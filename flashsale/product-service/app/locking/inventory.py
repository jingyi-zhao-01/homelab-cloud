import logging
import time

import psycopg
from psycopg.rows import dict_row

lock_logger = logging.getLogger("product-service.locking")


class InventoryReserveEngine:
    def __init__(
        self,
        database_url: str,
        lock_mode: str,
        retry_limit: int,
        slow_ms_threshold: float = 200,
    ) -> None:
        self._database_url = database_url
        self._lock_mode = lock_mode
        self._retry_limit = retry_limit
        self._slow_ms_threshold = slow_ms_threshold

    def reserve(self, product_id: int, quantity: int) -> dict[str, object] | None:
        if self._lock_mode == "optimistic":
            return self._reserve_optimistic(product_id, quantity)
        return self._reserve_pessimistic(product_id, quantity)

    def _reserve_pessimistic(
        self, product_id: int, quantity: int
    ) -> dict[str, object] | None:
        tx_start = time.perf_counter()
        try:
            with psycopg.connect(
                self._database_url, autocommit=False, row_factory=dict_row
            ) as conn:
                with conn.cursor() as cur:
                    lock_start = time.perf_counter()
                    cur.execute(
                        """
                        SELECT id, name, price, stock
                        FROM products
                        WHERE id = %s
                        FOR UPDATE
                        """,
                        (product_id,),
                    )
                    row = cur.fetchone()
                    lock_wait_ms = (time.perf_counter() - lock_start) * 1000
                    if lock_wait_ms >= self._slow_ms_threshold:
                        lock_logger.warning(
                            "event=lock_wait_slow lock_mode=pessimistic product_id=%s quantity=%s wait_ms=%.2f threshold_ms=%.2f",
                            product_id,
                            quantity,
                            lock_wait_ms,
                            self._slow_ms_threshold,
                        )

                    if not row:
                        return None

                    current_stock = int(row["stock"])
                    if current_stock < quantity:
                        lock_logger.warning(
                            "event=insufficient_stock lock_mode=pessimistic product_id=%s quantity=%s current_stock=%s",
                            product_id,
                            quantity,
                            current_stock,
                        )
                        raise ValueError("insufficient stock")

                    cur.execute(
                        """
                        UPDATE products
                        SET stock = stock - %s
                        WHERE id = %s
                        RETURNING id, name, price, stock
                        """,
                        (quantity, product_id),
                    )
                    updated = cur.fetchone()
                    if not updated:
                        lock_logger.error(
                            "event=pessimistic_reserve_failed lock_mode=pessimistic product_id=%s quantity=%s",
                            product_id,
                            quantity,
                        )
                        raise RuntimeError("pessimistic reserve failed")

                    conn.commit()
                    return updated
        except psycopg.Error:
            lock_logger.exception(
                "event=inventory_db_error lock_mode=pessimistic product_id=%s quantity=%s",
                product_id,
                quantity,
            )
            raise
        finally:
            tx_elapsed_ms = (time.perf_counter() - tx_start) * 1000
            if tx_elapsed_ms >= self._slow_ms_threshold:
                lock_logger.warning(
                    "event=transaction_slow lock_mode=pessimistic product_id=%s quantity=%s elapsed_ms=%.2f threshold_ms=%.2f",
                    product_id,
                    quantity,
                    tx_elapsed_ms,
                    self._slow_ms_threshold,
                )

    def _reserve_optimistic(
        self, product_id: int, quantity: int
    ) -> dict[str, object] | None:
        reserve_start = time.perf_counter()
        try:
            for retry_index in range(self._retry_limit):
                with psycopg.connect(
                    self._database_url, autocommit=True, row_factory=dict_row
                ) as conn:
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

                        current_stock = int(row["stock"])
                        if current_stock < quantity:
                            lock_logger.warning(
                                "event=insufficient_stock lock_mode=optimistic product_id=%s quantity=%s current_stock=%s",
                                product_id,
                                quantity,
                                current_stock,
                            )
                            raise ValueError("insufficient stock")

                        cur.execute(
                            """
                            UPDATE products
                            SET stock = stock - %s
                            WHERE id = %s AND stock = %s
                            RETURNING id, name, price, stock
                            """,
                            (quantity, product_id, current_stock),
                        )
                        updated = cur.fetchone()
                        if updated:
                            if retry_index > 0:
                                elapsed_ms = (
                                    time.perf_counter() - reserve_start
                                ) * 1000
                                lock_logger.info(
                                    "event=optimistic_retry_succeeded lock_mode=optimistic product_id=%s quantity=%s retries_used=%s elapsed_ms=%.2f",
                                    product_id,
                                    quantity,
                                    retry_index,
                                    elapsed_ms,
                                )
                            return updated

                        lock_logger.warning(
                            "event=optimistic_conflict_retry lock_mode=optimistic product_id=%s quantity=%s retry_index=%s retry_limit=%s",
                            product_id,
                            quantity,
                            retry_index + 1,
                            self._retry_limit,
                        )

            lock_logger.warning(
                "event=optimistic_retry_exhausted lock_mode=optimistic product_id=%s quantity=%s retry_limit=%s",
                product_id,
                quantity,
                self._retry_limit,
            )
            raise RuntimeError("optimistic reserve retry limit exceeded")
        except psycopg.Error:
            lock_logger.exception(
                "event=inventory_db_error lock_mode=optimistic product_id=%s quantity=%s",
                product_id,
                quantity,
            )
            raise
