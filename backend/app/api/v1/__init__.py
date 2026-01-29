"""
API v1 Router

Aggregates all API v1 endpoints.
"""

from fastapi import APIRouter

from app.api.v1 import auth, users

router = APIRouter()

# Include sub-routers
router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(users.router, prefix="/users", tags=["Users"])

# Additional routers will be added as they're implemented:
# router.include_router(campaigns.router, prefix="/campaigns", tags=["Campaigns"])
# router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
# router.include_router(automation.router, prefix="/automation", tags=["Automation"])
# router.include_router(billing.router, prefix="/billing", tags=["Billing"])
# router.include_router(admin.router, prefix="/admin", tags=["Admin"])
