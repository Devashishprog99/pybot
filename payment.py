"""
Cashfree Payment Gateway Integration
"""
import asyncio
import qrcode
import os
import urllib3
# Suppress InsecureRequestWarning from Cashfree SDK
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
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
Cashfree.XEnvironment = Cashfree.PRODUCTION if config.CASHFREE_ENV.upper() == "PRODUCTION" else Cashfree.SANDBOX

class PaymentManager:
    
    @staticmethod
    async def create_payment_order(user_id: int, amount: float) -> dict:
        """Create a standard Cashfree order and return the bridge link"""
        try:
            order_id = generate_order_id()
            
            # Create customer details with valid 10-digit phone
            # Generate 10-digit phone number from user_id if not provided
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
                order_expiry_time=(datetime.utcnow() + timedelta(minutes=16)).strftime('%Y-%m-%dT%H:%M:%SZ')
            )
            
            x_api_version = "2023-08-01"
            order_response = Cashfree().PGCreateOrder(x_api_version, order_request)
            
            if not order_response or not order_response.data:
                return {'success': False, 'error': 'Failed to create order'}
                
            payment_session_id = order_response.data.payment_session_id
            
            # Determine the fastest/most reliable link
            if not config.DASHBOARD_URL or "localhost" in config.DASHBOARD_URL or "127.0.0.1" in config.DASHBOARD_URL:
                env_tag = "api" if config.CASHFREE_ENV.upper() == 'PRODUCTION' else "sandbox"
                payment_link = f"https://payments.{env_tag}.cashfree.com/order/#{payment_session_id}"
            else:
                # Use the professional bridge
                payment_link = f"{config.DASHBOARD_URL.rstrip('/')}/pay/{payment_session_id}"
            
            print(f"DEBUG: Generated Payment Link ({config.CASHFREE_ENV}): {payment_link}")
            
            # Save transaction
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
                'amount': amount,
                'txn_id': txn_id
            }
        except Exception as e:
            print(f"DEBUG: create_payment_order failed: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

    @staticmethod
    async def create_collect_payment(user_id: int, amount: float, upi_id: str) -> dict:
        """Create Cashfree order and send a UPI Collect request"""
        try:
            order_id = generate_order_id()
            phone_suffix = str(user_id)[-9:].zfill(9)
            user_phone = f"9{phone_suffix}"
            
            customer = CustomerDetails(
                customer_id=str(user_id),
                customer_phone=user_phone
            )
            
            order_request = CreateOrderRequest(
                order_amount=amount,
                order_currency="INR",
                order_id=order_id,
                customer_details=customer,
                order_expiry_time=(datetime.utcnow() + timedelta(minutes=16)).strftime('%Y-%m-%dT%H:%M:%SZ')
            )
            
            x_api_version = "2023-08-01"
            order_response = Cashfree().PGCreateOrder(x_api_version, order_request)
            
            if not order_response or not order_response.data:
                return {'success': False, 'error': 'Failed to create order'}
                
            payment_session_id = order_response.data.payment_session_id
            
            # 2. Call Pay Order with UPI COLLECT method
            upi_method = UPIPaymentMethod(
                upi=Upi(channel="collect", upi_id=upi_id)
            )
            pay_request = PayOrderRequest(
                payment_session_id=payment_session_id,
                payment_method=upi_method
            )
            
            try:
                pay_response = Cashfree().PGPayOrder(x_api_version, pay_request)
            except Exception as pay_err:
                # FALLBACK: Use bridge
                payment_link = f"{config.DASHBOARD_URL.rstrip('/')}/pay/{payment_session_id}" if "localhost" not in config.DASHBOARD_URL else f"https://payments.{'api' if config.CASHFREE_ENV.upper() == 'PRODUCTION' else 'sandbox'}.cashfree.com/order/#{payment_session_id}"
                
                txn_id = db.create_transaction(
                    user_id=user_id, txn_type='wallet_add', amount=amount,
                    cashfree_order_id=order_id, payment_link=payment_link,
                    description=f"Add {format_currency(amount)} via UPI Link ({upi_id})"
                )
                return {
                    'success': True, 'order_id': order_id, 'payment_link': payment_link,
                    'is_fallback': True, 'amount': amount, 'txn_id': txn_id
                }

            if pay_response and pay_response.data:
                txn_id = db.create_transaction(
                    user_id=user_id, txn_type='wallet_add', amount=amount,
                    cashfree_order_id=order_id, payment_link="UPI_COLLECT",
                    description=f"Add {format_currency(amount)} via UPI Collect ({upi_id})"
                )
                return {'success': True, 'order_id': order_id, 'txn_id': txn_id, 'amount': amount}
            return {'success': False, 'error': 'Failed to send collect request'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    async def create_qr_payment(user_id: int, amount: float) -> dict:
        """Create Cashfree order and generate a UPI QR code"""
        try:
            order_id = generate_order_id()
            phone_suffix = str(user_id)[-9:].zfill(9)
            user_phone = f"9{phone_suffix}"
            
            customer = CustomerDetails(
                customer_id=str(user_id),
                customer_phone=user_phone
            )
            
            order_request = CreateOrderRequest(
                order_amount=amount,
                order_currency="INR",
                order_id=order_id,
                customer_details=customer,
                order_expiry_time=(datetime.utcnow() + timedelta(minutes=16)).strftime('%Y-%m-%dT%H:%M:%SZ')
            )
            
            x_api_version = "2023-08-01"
            order_response = Cashfree().PGCreateOrder(x_api_version, order_request)
            
            if not order_response or not order_response.data:
                return {'success': False, 'error': 'Failed to create order'}
                
            payment_session_id = order_response.data.payment_session_id
            
            upi_method = UPIPaymentMethod(upi=Upi(channel="qrcode"))
            pay_request = PayOrderRequest(
                payment_session_id=payment_session_id,
                payment_method=upi_method
            )
            
            try:
                pay_response = Cashfree().PGPayOrder(x_api_version, pay_request)
            except Exception as pay_err:
                # FALLBACK: QR of Bridge Link
                qr_payload = f"{config.DASHBOARD_URL.rstrip('/')}/pay/{payment_session_id}"
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(qr_payload)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                os.makedirs('temp_qrs', exist_ok=True)
                qr_path = f"temp_qrs/qr_{order_id}.png"
                img.save(qr_path)
                
                txn_id = db.create_transaction(
                    user_id=user_id, txn_type='wallet_add', amount=amount,
                    cashfree_order_id=order_id, payment_link=qr_payload,
                    description=f"Add {format_currency(amount)} to wallet (Link QR)"
                )
                return {
                    'success': True, 'order_id': order_id, 'qr_path': qr_path,
                    'is_fallback': True, 'expiry': config.PAYMENT_TIMEOUT,
                    'txn_id': txn_id, 'amount': amount
                }

            if pay_response and pay_response.data:
                qr_payload = getattr(pay_response.data, 'payload', None) or getattr(pay_response.data, 'payment_link', None)
                if not qr_payload:
                    qr_payload = f"https://payments.cashfree.com/order/#{payment_session_id}"

                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(qr_payload)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                os.makedirs('temp_qrs', exist_ok=True)
                qr_path = f"temp_qrs/qr_{order_id}.png"
                img.save(qr_path)
                
                txn_id = db.create_transaction(
                    user_id=user_id, txn_type='wallet_add', amount=amount,
                    cashfree_order_id=order_id, payment_link=qr_payload,
                    description=f"Add {format_currency(amount)} to wallet via QR"
                )
                return {
                    'success': True, 'order_id': order_id, 'qr_path': qr_path,
                    'expiry': config.PAYMENT_TIMEOUT, 'txn_id': txn_id, 'amount': amount
                }
            return {'success': False, 'error': 'Failed to generate QR payload'}
        except Exception as e:
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
