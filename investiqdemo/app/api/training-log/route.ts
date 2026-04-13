// app/api/training-log/route.ts
import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
	const body = await req.text();
	const apiUrl = process.env.PYTHON_API_URL ?? "http://localhost:8000";

	try {
		const upstream = await fetch(`${apiUrl}/training/log`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body,
		});
		const data = await upstream.json();
		return new Response(JSON.stringify(data), {
			status: upstream.status,
			headers: { "Content-Type": "application/json" },
		});
	} catch (err) {
		console.error("[training-log proxy] error:", err);
		return new Response(JSON.stringify({ error: "Failed to log training data" }), {
			status: 502,
			headers: { "Content-Type": "application/json" },
		});
	}
}
