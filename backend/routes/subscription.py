from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.exceptions import HTTPException
from auth.utils import get_current_user
from prisma import Prisma, enums
from datetime import datetime, timedelta, timezone
import stripe
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

db = Prisma()

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
async def stripe_webhook(
    request: Request, stripe_signature: str = Header(None)
):
    """Handle Stripe webhooks."""
    
    payload = await request.body()
    
    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, os.getenv("STRIPE_API_KEY"))
    except stripe.error.SignatureVerificationError as e:
        return HTTPException(400, "Failed to establish Stripe webhook signature")

    event_type = event["type"]
    data_object = event["data"]["object"]

    try:
        await db.connect()

        if event_type == "checkout.session.completed":
            session = await stripe.checkout.Session.retrieve(
                data_object["id"], expand=["line_items"]
            )
            customer_id = session.get("customer")
            customer = await stripe.Customer.retrieve(customer_id)
            price_id = session["line_items"]["data"][0]["price"]["id"]

            if not customer.get("email"):
                raise ValueError("No user email found")

            user = await db.userinstance.find_unique(where={"email": customer["email"]})


        elif event_type == "customer.subscription.deleted":
            subscription = await stripe.Subscription.retrieve(data_object["id"])
            user = await db.userinstance.find_unique(where={"customerId": subscription["customer"]})


    except Exception as e:
        return HTTPException(400, e)
    finally:
        await db.disconnect()

    return {"success": True}
    