import traceback
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import init_db, get_db_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database and tables on startup
    init_db()
    yield


app = FastAPI(title="Verdict Backend", version="1.0.0", lifespan=lifespan)

# Enable CORS for Next.js frontend (default port 3000) or other clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Mock payment service to simulate payment processing and failure traces
class PaymentService:
    def charge(self, payment_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Simulate payment processing.
        Raises ValueError if payment data is missing, null, or lacks an amount.
        """
        if payment_data is None:
            raise ValueError("payment_service.charge: Payment payload is null or missing")
        
        if not isinstance(payment_data, dict):
            raise TypeError(f"payment_service.charge: Expected dict for payment_data, got {type(payment_data).__name__}")

        amount = payment_data.get("amount")
        if amount is None or amount <= 0:
            raise ValueError(f"payment_service.charge: Invalid or missing payment amount: {amount}")

        return {
            "status": "charged",
            "amount": amount,
            "transaction_id": "txn_mock_verdict_12345"
        }


payment_service = PaymentService()


@app.get("/health")
def health_check():
    """Health check route."""
    return {
        "status": "ok",
        "service": "verdict-backend"
    }


@app.get("/db-status")
def db_status():
    """Database connectivity status check."""
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1")
        conn.close()
        return {
            "database": "connected",
            "status": "ok"
        }
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "database": "error",
                "status": "failed",
                "detail": str(exc)
            }
        )


@app.post("/checkout")
async def checkout(request: Request):
    """
    Deliberate failure checkout endpoint for regression/failure demonstrations.
    Intentionally returns HTTP 500 when payment data is missing/null,
    including a detailed payment_service.charge traceback.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    payment_data = body.get("payment") if isinstance(body, dict) else None

    try:
        # Deliberately invoke payment_service.charge
        charge_result = payment_service.charge(payment_data)
        return {
            "status": "success",
            "order_status": "completed",
            "payment": charge_result
        }
    except Exception as exc:
        # Capture formatted traceback from payment_service.charge failure
        tb_str = traceback.format_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Payment processing failed in checkout",
                "error_type": type(exc).__name__,
                "detail": str(exc),
                "traceback": tb_str
            }
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
