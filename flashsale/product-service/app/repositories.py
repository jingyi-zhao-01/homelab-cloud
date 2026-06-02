import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from itertools import count
from threading import Lock

import psycopg
from psycopg.rows import dict_row

from .config import (
    DEFAULT_SEED_PRODUCT_COUNT,
    INVENTORY_LOCK_MODE,
    OPTIMISTIC_RETRY_LIMIT,
    RESERVE_SQL_LOG_SLOW_MS,
)
from .locking import InventoryReserveEngine
from .models import ProductCreate, ProductOut, ReservationOut

db_logger = logging.getLogger("product-service.db")
RESERVATION_TTL_SECONDS = 300


def seed_items(
    count_value: int = DEFAULT_SEED_PRODUCT_COUNT,
) -> list[tuple[str, float, int]]:
    return [
        (
            f"Seed Item {idx}",
            round(9.9 + idx * 0.5, 2),
            10 + (idx % 15),
        )
        for idx in range(1, count_value + 1)
    ]


class ProductRepository(ABC):
    @abstractmethod
    def init_db(self) -> None:
        pass

    @abstractmethod
    def seed_if_empty(self) -> None:
        pass

    @abstractmethod
    def reset_db(self) -> None:
        pass

    @abstractmethod
    def seed_with_quantity(self, count: int, quantity: int) -> None:
        pass

    @abstractmethod
    def create_product(self, payload: ProductCreate) -> ProductOut:
        pass

    @abstractmethod
    def get_product(self, product_id: int) -> ProductOut | None:
        pass

    @abstractmethod
    def reserve_product(
        self, product_id: int, quantity: int
    ) -> ReservationOut | None:
        pass

    @abstractmethod
    def confirm_reservation(self, reservation_id: int) -> ReservationOut | None:
        pass

    @abstractmethod
    def cancel_reservation(self, reservation_id: int) -> ReservationOut | None:
        pass

    @abstractmethod
    def expire_reservations(self) -> int:
        pass

    @abstractmethod
    def has_product(self, product_id: int) -> bool:
        pass

    @abstractmethod
    def list_products(self) -> list[ProductOut]:
        pass


class InMemoryProductRepository(ProductRepository):
    def __init__(self) -> None:
        self._products: dict[int, ProductOut] = {}
        self._reservations: dict[int, ReservationOut] = {}
        self._counter = count(1)
        self._reservation_counter = count(1)
        self._lock = Lock()

    @staticmethod
    def _reservation_expiry() -> str:
        return (
            datetime.now(timezone.utc) + timedelta(seconds=RESERVATION_TTL_SECONDS)
        ).isoformat()

    def init_db(self) -> None:
        return

    def seed_if_empty(self) -> None:
        with self._lock:
            if self._products:
                return
            for idx, (name, price, stock) in enumerate(seed_items(), start=1):
                self._products[idx] = ProductOut(
                    id=idx, name=name, price=price, stock=stock
                )
            self._counter = count(len(self._products) + 1)

    def reset_db(self) -> None:
        with self._lock:
            self._products.clear()
            self._reservations.clear()
            self._counter = count(1)
            self._reservation_counter = count(1)

    def seed_with_quantity(self, count_value: int, quantity: int) -> None:
        with self._lock:
            self._products.clear()
            self._reservations.clear()
            for idx in range(1, count_value + 1):
                self._products[idx] = ProductOut(
                    id=idx,
                    name=f"Seed Item {idx}",
                    price=round(9.9 + idx * 0.5, 2),
                    stock=quantity,
                )
            self._counter = count(count_value + 1)
            self._reservation_counter = count(1)

    def create_product(self, payload: ProductCreate) -> ProductOut:
        with self._lock:
            product_id = next(self._counter)
            product = ProductOut(
                id=product_id,
                name=payload.name,
                price=payload.price,
                stock=payload.stock,
            )
            self._products[product_id] = product
            return product

    def get_product(self, product_id: int) -> ProductOut | None:
        return self._products.get(product_id)

    def reserve_product(
        self, product_id: int, quantity: int
    ) -> ReservationOut | None:
        with self._lock:
            product = self._products.get(product_id)
            if not product:
                return None
            if product.stock < quantity:
                raise ValueError("insufficient stock")
            updated = ProductOut(
                id=product.id,
                name=product.name,
                price=product.price,
                stock=product.stock - quantity,
            )
            self._products[product_id] = updated
            reservation_id = next(self._reservation_counter)
            reservation = ReservationOut(
                reservation_id=reservation_id,
                product_id=product_id,
                quantity=quantity,
                status="reserved",
                expires_at=self._reservation_expiry(),
            )
            self._reservations[reservation_id] = reservation
            return reservation

    def confirm_reservation(self, reservation_id: int) -> ReservationOut | None:
        with self._lock:
            reservation = self._reservations.get(reservation_id)
            if not reservation:
                return None
            if reservation.status != "reserved":
                return reservation
            updated = ReservationOut(
                reservation_id=reservation.reservation_id,
                product_id=reservation.product_id,
                quantity=reservation.quantity,
                status="confirmed",
                expires_at=reservation.expires_at,
            )
            self._reservations[reservation_id] = updated
            return updated

    def cancel_reservation(self, reservation_id: int) -> ReservationOut | None:
        with self._lock:
            reservation = self._reservations.get(reservation_id)
            if not reservation:
                return None
            if reservation.status != "reserved":
                return reservation
            product = self._products.get(reservation.product_id)
            if not product:
                return None
            self._products[reservation.product_id] = ProductOut(
                id=product.id,
                name=product.name,
                price=product.price,
                stock=product.stock + reservation.quantity,
            )
            updated = ReservationOut(
                reservation_id=reservation.reservation_id,
                product_id=reservation.product_id,
                quantity=reservation.quantity,
                status="cancelled",
                expires_at=reservation.expires_at,
            )
            self._reservations[reservation_id] = updated
            return updated

    def expire_reservations(self) -> int:
        now = datetime.now(timezone.utc)
        expired_count = 0
        with self._lock:
            for reservation_id, reservation in list(self._reservations.items()):
                if reservation.status != "reserved" or not reservation.expires_at:
                    continue
                if datetime.fromisoformat(reservation.expires_at) > now:
                    continue
                product = self._products.get(reservation.product_id)
                if not product:
                    continue
                self._products[reservation.product_id] = ProductOut(
                    id=product.id,
                    name=product.name,
                    price=product.price,
                    stock=product.stock + reservation.quantity,
                )
                self._reservations[reservation_id] = ReservationOut(
                    reservation_id=reservation.reservation_id,
                    product_id=reservation.product_id,
                    quantity=reservation.quantity,
                    status="expired",
                    expires_at=reservation.expires_at,
                )
                expired_count += 1
        return expired_count

    def has_product(self, product_id: int) -> bool:
        return product_id in self._products

    def list_products(self) -> list[ProductOut]:
        return list(self._products.values())


class PostgresProductRepository(ProductRepository):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._inventory_lock_mode = INVENTORY_LOCK_MODE
        self._reserve_engine = InventoryReserveEngine(
            database_url=database_url,
            lock_mode=INVENTORY_LOCK_MODE,
            retry_limit=OPTIMISTIC_RETRY_LIMIT,
            slow_ms_threshold=RESERVE_SQL_LOG_SLOW_MS,
        )

    @staticmethod
    def _to_product(row: dict[str, object]) -> ProductOut:
        return ProductOut(
            id=int(row["id"]),
            name=str(row["name"]),
            price=float(row["price"]),
            stock=int(row["stock"]),
        )

    def init_db(self) -> None:
        with psycopg.connect(self._database_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS products (
                        id BIGSERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        price NUMERIC(12, 2) NOT NULL,
                        stock INTEGER NOT NULL CHECK (stock >= 0)
                    )
                    """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS reservations (
                        reservation_id BIGSERIAL PRIMARY KEY,
                        product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                        quantity INTEGER NOT NULL CHECK (quantity > 0),
                        status TEXT NOT NULL,
                        expires_at TIMESTAMPTZ NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """)

    def seed_if_empty(self) -> None:
        with psycopg.connect(
            self._database_url, autocommit=True, row_factory=dict_row
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS count FROM products")
                row = cur.fetchone()
                if row and int(row["count"]) > 0:
                    return
                cur.executemany(
                    """
                    INSERT INTO products (name, price, stock)
                    VALUES (%s, %s, %s)
                    """,
                    seed_items(),
                )

    def reset_db(self) -> None:
        with psycopg.connect(self._database_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE reservations RESTART IDENTITY CASCADE")
                cur.execute("TRUNCATE TABLE products RESTART IDENTITY CASCADE")

    def seed_with_quantity(self, count_value: int, quantity: int) -> None:
        with psycopg.connect(
            self._database_url, autocommit=True, row_factory=dict_row
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE reservations RESTART IDENTITY CASCADE")
                cur.execute("TRUNCATE TABLE products RESTART IDENTITY CASCADE")
                items_to_seed = [
                    (f"Seed Item {idx}", round(9.9 + idx * 0.5, 2), quantity)
                    for idx in range(1, count_value + 1)
                ]
                cur.executemany(
                    """
                    INSERT INTO products (name, price, stock)
                    VALUES (%s, %s, %s)
                    """,
                    items_to_seed,
                )

    def create_product(self, payload: ProductCreate) -> ProductOut:
        with psycopg.connect(
            self._database_url, autocommit=True, row_factory=dict_row
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO products (name, price, stock)
                    VALUES (%s, %s, %s)
                    RETURNING id, name, price, stock
                    """,
                    (payload.name, payload.price, payload.stock),
                )
                row = cur.fetchone()
                if not row:
                    raise RuntimeError("product persistence failed")
                return ProductOut(
                    id=int(row["id"]),
                    name=str(row["name"]),
                    price=float(row["price"]),
                    stock=int(row["stock"]),
                )

    def get_product(self, product_id: int) -> ProductOut | None:
        with psycopg.connect(self._database_url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, name, price, stock
                    FROM products
                    WHERE id = %s
                    """,
                    (product_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return ProductOut(
                    id=int(row["id"]),
                    name=str(row["name"]),
                    price=float(row["price"]),
                    stock=int(row["stock"]),
                )

    def reserve_product(
        self, product_id: int, quantity: int
    ) -> ReservationOut | None:
        start = time.perf_counter()
        result = "updated"
        try:
            updated_row = self._reserve_engine.reserve(product_id, quantity)

            if not updated_row:
                result = "missing"
                return None
            with psycopg.connect(
                self._database_url, autocommit=True, row_factory=dict_row
            ) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO reservations (product_id, quantity, status, expires_at)
                        VALUES (%s, %s, %s, NOW() + (%s || ' seconds')::interval)
                        RETURNING reservation_id, product_id, quantity, status, expires_at
                        """,
                        (product_id, quantity, "reserved", RESERVATION_TTL_SECONDS),
                    )
                    reservation_row = cur.fetchone()
                    if not reservation_row:
                        raise RuntimeError("reservation persistence failed")
                    return ReservationOut(
                        reservation_id=int(reservation_row["reservation_id"]),
                        product_id=int(reservation_row["product_id"]),
                        quantity=int(reservation_row["quantity"]),
                        status=str(reservation_row["status"]),
                        expires_at=reservation_row["expires_at"].isoformat()
                        if reservation_row["expires_at"]
                        else None,
                    )
        except ValueError:
            result = "insufficient_stock"
            raise
        except RuntimeError:
            result = "retry_exhausted"
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            if elapsed_ms >= RESERVE_SQL_LOG_SLOW_MS:
                db_logger.warning(
                    "event=reserve_sql_slow product_id=%s quantity=%s elapsed_ms=%.2f result=%s lock_mode=%s",
                    product_id,
                    quantity,
                    elapsed_ms,
                    result,
                    self._inventory_lock_mode,
                )

    def confirm_reservation(self, reservation_id: int) -> ReservationOut | None:
        with psycopg.connect(
            self._database_url, autocommit=True, row_factory=dict_row
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE reservations
                    SET status = CASE WHEN status = 'reserved' THEN 'confirmed' ELSE status END
                    WHERE reservation_id = %s
                    RETURNING reservation_id, product_id, quantity, status, expires_at
                    """,
                    (reservation_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return ReservationOut(
                    reservation_id=int(row["reservation_id"]),
                    product_id=int(row["product_id"]),
                    quantity=int(row["quantity"]),
                    status=str(row["status"]),
                    expires_at=row["expires_at"].isoformat() if row["expires_at"] else None,
                )

    def cancel_reservation(self, reservation_id: int) -> ReservationOut | None:
        with psycopg.connect(
            self._database_url, autocommit=False, row_factory=dict_row
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT reservation_id, product_id, quantity, status, expires_at
                    FROM reservations
                    WHERE reservation_id = %s
                    FOR UPDATE
                    """,
                    (reservation_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                if str(row["status"]) == "reserved":
                    cur.execute(
                        "UPDATE products SET stock = stock + %s WHERE id = %s",
                        (int(row["quantity"]), int(row["product_id"])),
                    )
                    cur.execute(
                        """
                        UPDATE reservations
                        SET status = 'cancelled'
                        WHERE reservation_id = %s
                        RETURNING reservation_id, product_id, quantity, status, expires_at
                        """,
                        (reservation_id,),
                    )
                    row = cur.fetchone()
                conn.commit()
                return ReservationOut(
                    reservation_id=int(row["reservation_id"]),
                    product_id=int(row["product_id"]),
                    quantity=int(row["quantity"]),
                    status=str(row["status"]),
                    expires_at=row["expires_at"].isoformat() if row["expires_at"] else None,
                )

    def expire_reservations(self) -> int:
        expired_count = 0
        with psycopg.connect(
            self._database_url, autocommit=False, row_factory=dict_row
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT reservation_id, product_id, quantity
                    FROM reservations
                    WHERE status = 'reserved' AND expires_at <= NOW()
                    FOR UPDATE
                    """
                )
                rows = cur.fetchall()
                for row in rows:
                    cur.execute(
                        "UPDATE products SET stock = stock + %s WHERE id = %s",
                        (int(row["quantity"]), int(row["product_id"])),
                    )
                    cur.execute(
                        "UPDATE reservations SET status = 'expired' WHERE reservation_id = %s",
                        (int(row["reservation_id"]),),
                    )
                    expired_count += 1
                conn.commit()
        return expired_count

    def has_product(self, product_id: int) -> bool:
        with psycopg.connect(self._database_url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM products WHERE id = %s", (product_id,))
                return cur.fetchone() is not None

    def release_product(self, product_id: int, quantity: int) -> ProductOut | None:
        with psycopg.connect(
            self._database_url, autocommit=True, row_factory=dict_row
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE products
                    SET stock = stock + %s
                    WHERE id = %s
                    RETURNING id, name, price, stock
                    """,
                    (quantity, product_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return self._to_product(row)

    def list_products(self) -> list[ProductOut]:
        with psycopg.connect(self._database_url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name, price, stock
                    FROM products
                    ORDER BY id DESC
                    """)
                rows = cur.fetchall()
                return [
                    ProductOut(
                        id=int(row["id"]),
                        name=str(row["name"]),
                        price=float(row["price"]),
                        stock=int(row["stock"]),
                    )
                    for row in rows
                ]
