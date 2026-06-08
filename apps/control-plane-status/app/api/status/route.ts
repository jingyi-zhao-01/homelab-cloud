import { NextResponse } from "next/server";
import { getDashboardSnapshot } from "@/lib/status";

export const revalidate = 60;

export async function GET() {
  const snapshot = await getDashboardSnapshot();
  return NextResponse.json(snapshot);
}
