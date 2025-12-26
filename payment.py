"""
Cashfree Payment Gateway Integration
"""
import asyncio
import qrcode
import os
from io import BytesIO
from datetime import datetime, timedelta
from cashfree_pg.models.create_order_request import CreateOrderRequest
from cashfree_pg.models.customer_details import CustomerDetails
from cashfree_pg.models.order_meta import OrderMeta
from cashfree_pg.api_client import Cashfree
from cashfree_pg.models.pay_order_request import PayOrderRequest
from cashfree_pg.models.upi_payment_method import UPIPaymentMethod
from cashfree_pg.models.upi import Upi
import config
from mongodb import db
from utils import generate_order_id, format_currency

# Configure Cashfree
Cashfree.XClientId = config.CASHFREE_APP_ID
Cashfree.XClientSecret = config.CASHFREE_SECRET_KEY
Cashfree.XEnvironment = Cashfree.PRODUCTION if config.CASHFREE_ENV == "PRODUCTION" else Cashfree.SANDBOX

class PaymentManager:
    
    @staticmethod
    async def create_qr_payment(user_id: int, amount: float, user_phone: str = None) -> dict:
        """Create Cashfree order and generate a UPI QR code image"""
        try:
            order_id = generate_order_id()
            
            if not user_phone:
                phone_suffix = str(user_id)[-9:].zfill(9)
                user_phone = f"9{phone_suffix}"
            
            customer = CustomerDetails(
                customer_id=str(user_id),
                customer_phone=user_phone
            )
            
            # 1. Create Order
            order_request = CreateOrderRequest(
                order_amount=amount,
                order_currency="INR",
                order_id=order_id,
                customer_details=customer,
                order_meta=OrderMeta(
                    notify_url=f"https://your-domain.com/webhook" # This should be your actual webhook
                ),
                order_expiry_time=(datetime.utcnow() + timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%SZ')
            )
            
            x_api_version = "2023-08-01"
            order_response = Cashfree().PGCreateOrder(x_api_version, order_request)
            
            if not order_response or not order_response.data:
                return {'success': False, 'error': 'Failed to create order'}
                
            payment_session_id = order_response.data.payment_session_id
            
            # 2. Call Pay Order with UPI QR method
            upi_method = UPIPaymentMethod(
                upi=Upi(
                    channel="qrcode",
                    # Some versions might require a dummy upi_id for qrcode channel, 
                    # but usually channel 'qrcode' doesn't need it.
                )
            )
            
            pay_request = PayOrderRequest(
                payment_session_id=payment_session_id,
                payment_method=upi_method
            )
            
            pay_response = Cashfree().PGPayOrder(x_api_version, pay_request)
            
            # Debug logging
            print(f"DEBUG: Pay Response: {pay_response}")
            
            if pay_response and pay_response.data:
                # In Cashfree SDK v4, for UPI QR, the link is usually in data.data or data.payload
                qr_payload = None
                data_obj = pay_response.data
                
                # Try all possible locations for the UPI intent / payload
                if hasattr(data_obj, 'data') and data_obj.data:
                    if isinstance(data_obj.data, dict):
                        qr_payload = data_obj.data.get('payload') or data_obj.data.get('qr_code')
                    else:
                        qr_payload = getattr(data_obj.data, 'payload', None) or getattr(data_obj.data, 'qr_code', None)
                
                if not qr_payload and hasattr(data_obj, 'payload'):
                    qr_payload = data_obj.payload
                
                if not qr_payload:
                    # Final fallback: if we can't find the raw payload, we use the payment_link if it exists
                    qr_payload = getattr(data_obj, 'payment_link', None)
                    if not qr_payload:
                        qr_payload = f"https://payments.cashfree.com/order/#{payment_session_id}"
                        print(f"DEBUG: Using fallback web link for QR: {qr_payload}")

                # 3. Generate QR Image
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(qr_payload)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                
                # Save to temporary path
                os.makedirs('temp_qrs', exist_ok=True)
                qr_path = f"temp_qrs/qr_{order_id}.png"
                img.save(qr_path)
                
                # Save transaction
                txn_id = db.create_transaction(
                    user_id=user_id,
                    txn_type='wallet_add',
                    amount=amount,
                    cashfree_order_id=order_id,
                    payment_link=qr_payload,
                    description=f"Add {format_currency(amount)} to wallet via QR"
                )
                
                return {
                    'success': True,
                    'order_id': order_id,
                    'qr_path': qr_path,
                    'expiry': 300, # 5 minutes
                    'txn_id': txn_id,
                    'amount': amount
                }
                
            return {'success': False, 'error': 'Failed to generate QR payload'}
            
        except Exception as e:
            print(f"QR Payment error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

    @staticmethod
    async def create_payment_order(user_id: int, amount: float, user_phone: str = None) -> dict:
        """Create Cashfree payment order"""
        try:
            order_id = generate_order_id()
            
            # Create customer details with valid 10-digit phone
            if not user_phone:
                # Generate 10-digit phone number from user_id
                phone_suffix = str(user_id)[-9:].zfill(9)  # Last 9 digits, padded with zeros
                user_phone = f"9{phone_suffix}"  # Start with 9, total 10 digits
            
            customer = CustomerDetails(
                customer_id=str(user_id),
                customer_phone=user_phone
            )
            
            # Create order request
            order_request = CreateOrderRequest(
                order_amount=amount,
                order_currency="INR",
                order_id=order_id,
                customer_details=customer
            )
            
            # Create order using Cashfree SDK
            x_api_version = "2023-08-01"
            api_response = Cashfree().PGCreateOrder(x_api_version, order_request)
            
            if api_response and api_response.data:
                order_data = api_response.data
                # Generate payment link from payment_session_id
                payment_session_id = order_data.payment_session_id if hasattr(order_data, 'payment_session_id') else None
                
                if payment_session_id:
                    # Cashfree payment link format
                    env = "api" if config.CASHFREE_ENV == "PRODUCTION" else "sandbox"
                    payment_link = f"https://payments.{env}.cashfree.com/order/#{payment_session_id}"
                else:
                    return {'success': False, 'error': 'No payment session ID received'}
                
                # Save transaction to database
                txn_id = db.create_transaction(
                    user_id=user_id,
                    txn_type='wallet_add',
                    amount=amount,
                    cashfree_order_id=order_id,
                    payment_link=payment_link,
                    description=f"Add {format_currency(amount)} to wallet"
                )
                
                return {
                    'success': True,
                    'order_id': order_id,
                    'payment_link': payment_link,
                    'txn_id': txn_id,
                    'amount': amount
                }
            else:
                return {'success': False, 'error': 'Failed to create order - no response data'}
                
        except Exception as e:
            print(f"Payment order creation error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def check_payment_status(order_id: str) -> dict:
        """Check payment status from Cashfree"""
        try:
            x_api_version = "2023-08-01"
            api_response = Cashfree().PGOrderFetchPayments(x_api_version, order_id)
            
            if api_response and api_response.data and len(api_response.data) > 0:
                payment = api_response.data[0]
                return {
                    'success': True,
                    'status': payment.payment_status if hasattr(payment, 'payment_status') else 'PENDING',
                    'amount': payment.payment_amount if hasattr(payment, 'payment_amount') else 0,
                    'payment_time': payment.payment_time if hasattr(payment, 'payment_time') else None
                }
            
            return {'success': False, 'status': 'PENDING'}
            
        except Exception as e:
            print(f"Payment status check error: {e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def verify_payment(order_id: str) -> bool:
        """Verify and process successful payment"""
        try:
            # Get transaction from database
            txn = db.get_transaction_by_order_id(order_id)
            if not txn:
                return False
            
            # Check if already processed
            if txn['status'] == 'success':
                return True
            
            # Check payment status
            result = await PaymentManager.check_payment_status(order_id)
            
            if result.get('success') and result.get('status') == 'SUCCESS':
                # Update wallet
                db.update_wallet(txn['user_id'], txn['amount'])
                
                # Update transaction status
                db.update_transaction_status(txn['txn_id'], 'success')
                
                return True
            
            return False
            
        except Exception as e:
            print(f"Payment verification error: {e}")
            return False
    
    @staticmethod
    async def cancel_payment(order_id: str) -> bool:
        """Cancel pending payment"""
        try:
            txn = db.get_transaction_by_order_id(order_id)
            if txn and txn['status'] == 'pending':
                db.update_transaction_status(txn['txn_id'], 'cancelled')
                return True
            return False
        except Exception as e:
            print(f"Payment cancellation error: {e}")
            return False
    
    @staticmethod
    async def monitor_payment(order_id: str, timeout: int = None) -> str:
        """Monitor payment status with timeout"""
        timeout = timeout or config.PAYMENT_TIMEOUT
        start_time = datetime.now()
        
        while (datetime.now() - start_time).seconds < timeout:
            result = await PaymentManager.check_payment_status(order_id)
            
            if result.get('success'):
                status = result.get('status')
                if status in ['SUCCESS', 'FAILED']:
                    return status
            
            # Check every 5 seconds
            await asyncio.sleep(5)
        
        # Timeout - mark as failed
        txn = db.get_transaction_by_order_id(order_id)
        if txn and txn['status'] == 'pending':
            db.update_transaction_status(txn['txn_id'], 'failed')
        
        return 'TIMEOUT'

payment_manager = PaymentManager()
