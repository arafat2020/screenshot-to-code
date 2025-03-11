from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.exceptions import HTTPException
from auth.utils import get_current_user
from prisma import Prisma, enums
from datetime import datetime, timedelta, timezone
import stripe
import os
from dotenv import load_dotenv
import stripe.error

load_dotenv()

router = APIRouter()

db = Prisma()
webhook_secret = os.getenv("STRIPE_API_KEY")

@router.post('/free_subscriptions')
async def get_free_subscriptions(payload = Depends(get_current_user)):
    """Subscribe to free subscription."""
    await db.connect()
    # Get the current time
    now = datetime.now(timezone.utc)
    # Check if the user already has an active subscription
    existing_subscription = await db.subscription.find_first(
        where={
            "userId": payload["id"],
            "expiryDate": {
                "gt": now  # Check if subscription is still valid
            }
        }
    )
    
    if existing_subscription:
        raise HTTPException(status_code=400, detail="User already has an active subscription.")

    # Create new free subscription
    free_sub = await db.subscription.create(
        data={
            "planType": enums.SubscriptionPlanType.FREE,
            "userId": payload["id"],
            "startDate": now,
            "expiryDate": now + timedelta(days=30)  # Free subscription lasts for 30 days
        }
    )
    
    await db.disconnect()

    return {
        "message": "Free subscription created successfully",
        "subscription": free_sub
    }
    

@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    """Handle Stripe webhooks securely."""
    if not webhook_secret:
        raise HTTPException(status_code=500, detail="Webhook secret is not set.")

    payload = await request.body()  # Get raw request body
    try:
        # Verify and construct the event using Stripe's secret
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        print(stripe.error.SignatureVerificationError)
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    data_object = event["data"]["object"]

    print(f"🔹 Received event: {event_type}")  # Log event type

    # Handle specific event types
    if event_type == "checkout.session.completed":
        print("✅ Payment successful for session:", data_object["id"])

    elif event_type == "invoice.paid":
        print("✅ Invoice paid:", data_object["id"])

    elif event_type == "customer.subscription.deleted":
        print("⚠️ Subscription canceled for:", data_object["customer"])

    # Respond to Stripe that the webhook was received successfully
    return {"status": "success"}


@router.post("/create-subscription")
async def create_subscription(email: str, priceId: str):
    try:
        session = stripe.checkout.Session.create(
            api_key=os.getenv("STRIPE_SECRET"),
            payment_method_types=["card"],
            mode="subscription",  # Ensure it's a recurring subscription
            customer_email=email,  # Pre-fill email
            line_items=[
                {
                    "price": priceId,  # Recurring monthly price ßfrom Stripe
                    "quantity": 1,
                }
            ],
            success_url="https://your-site.com/success",
            cancel_url="https://your-site.com/cancel",
        )
        return {"url": session.url}  # Redirect user to Stripe Checkout
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))