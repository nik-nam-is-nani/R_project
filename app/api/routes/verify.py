from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.schemas.certificate import VerificationResponse
from app.services.certificate_service import verify_certificate_by_code

router = APIRouter(prefix="/verify", tags=["Verification"])


@router.get("/{verification_code}", response_model=VerificationResponse, summary="Verify certificate authenticity")
def verify_certificate(verification_code: str, db: Session = Depends(get_db)):
    """
    Public verification endpoint to validate certificate authenticity by unique verification code.
    Returns status valid=true with issued certificate details, or valid=false.
    """
    res = verify_certificate_by_code(db, verification_code)
    return res
