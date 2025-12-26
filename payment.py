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

# Global to store last API response for diagnostic /logs command
LAST_API_RESPONSE = "No API calls made yet."
LAST_GENERATED_LINK = "None"

class PaymentManager:
    
    @staticmethod
    def get_last_response():
        return f"{LAST_API_RESPONSE}\n\nGenerated Link: {LAST_GENERATED_LINK}"

    @staticmethod
    async def create_payment_order(user_id: int, amount: float) -> dict:
        """Create a standard Cashfree order and return the bridge link"""
        global LAST_API_RESPONSE, LAST_GENERATED_LINK
        try:
            order_id = generate_order_id()
            
            # Create customer details with valid 10-digit phone
            phone_suffix = str(user_id)[-9:].zfill(9)
            user_phone = f"9{phone_suffix}"
            
            customer = CustomerDetails(
                customer_id=str(user_id),
                customer_phone=user_phone
            )
            
            # 1. Create Order with OrderMeta (required for payment_link generation)
            # Use a dummy return_url to trigger the generation of a native link
            dash_url = config.DASHBOARD_URL.rstrip('/')
            if dash_url and not dash_url.startswith('http'):
                dash_url = f"https://{dash_url}"
            
            # CRITICAL FIX: Redirect to /close route to auto-close Web App
            # return_url = f"{dash_url}/" if dash_url else "https://t.me/BotFather"
            return_url = f"{dash_url}/close" if dash_url else f"https://t.me/{config.BOT_USERNAME}"
            
            order_meta = OrderMeta(
                return_url=return_url
            )
            
            order_request = CreateOrderRequest(
                order_amount=amount,
                order_currency="INR",
                order_id=order_id,
                customer_details=customer,
                order_meta=order_meta,
                order_expiry_time=(datetime.utcnow() + timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
            )
            
            x_api_version = "2023-08-01"
            order_response = Cashfree().PGCreateOrder(x_api_version, order_request)
            
            # Save for diagnostics
            LAST_API_RESPONSE = f"Status: {order_response.status_code if hasattr(order_response, 'status_code') else 'Unknown'}\nData: {order_response.data if order_response else 'None'}"

            if not order_response or not order_response.data:
                return {'success': False, 'error': 'Failed to create order'}
                
            payment_session_id = order_response.data.payment_session_id
            
            # Determine payment link
            # Priority 1: Use the native payment_link from response if available
            raw_link = getattr(order_response.data, 'payment_link', None)
            
            # Fallback construction if raw_link missing
            if not raw_link:
                 if config.CASHFREE_ENV.upper() == 'PRODUCTION':
                      raw_link = f"https://payments.cashfree.com/order/#/{payment_session_id}"
                 else:
                      raw_link = f"https://sandbox.cashfree.com/pg/checkout/order/#/{payment_session_id}"

            # Bridge Logic
            payment_link = getattr(order_response.data, 'payment_link', None)

            # Request UPI QR Payload separately
            try:
                base_url = "https://api.cashfree.com/pg" if config.CASHFREE_ENV.upper() == 'PRODUCTION' else "https://sandbox.cashfree.com/pg"
                r = requests.post(
                    f"{base_url}/orders/{order_id}/pay",
                    headers={
                        "x-api-version": "2023-08-01",
                        "x-client-id": config.CASHFREE_APP_ID,
                        "x-client-secret": config.CASHFREE_SECRET_KEY
                    },
                    json={
                        "payment_session_id": payment_session_id,
                        "payment_method": {
                            "upi": {
                                "channel": "qrcode"
                            }
                        }
                    },
                    timeout=5
                )
                if r.status_code == 200:
                    data = r.json()
                    # extract 'qrcode' string from payload
                    if 'data' in data and 'payload' in data['data']:
                        raw_link = data['data']['payload'].get('qrcode')
            except Exception as e:
                print(f"DTO - Failed to fetch UPI QR: {e}")
                import traceback
                traceback.print_exc()

            # Fallback to standard link if extraction failed
            if not raw_link:
                 if config.CASHFREE_ENV.upper() == 'PRODUCTION':
                      raw_link = f"https://payments.cashfree.com/order/#/{payment_session_id}"
                 else:
                      raw_link = f"https://sandbox.cashfree.com/pg/checkout/order/#/{payment_session_id}"

            # Bridge Logic
            payment_link = raw_link # Default to raw
            if config.USE_PAYMENT_BRIDGE and config.DASHBOARD_URL and "localhost" not in config.DASHBOARD_URL:
                 env_tag = config.CASHFREE_ENV.upper()
                 payment_link = f"{config.DASHBOARD_URL.rstrip('/')}/pay/{env_tag}/{payment_session_id}"
            
            LAST_GENERATED_LINK = payment_link
            print(f"DEBUG: Generated Links - Bridge: {payment_link}, Raw: {raw_link}")
            
            # Save transaction
            txn_id = db.create_transaction(
                user_id=user_id,
                txn_type='wallet_add',
                amount=amount,
                cashfree_order_id=order_id,
                payment_link=payment_link, # Saves the Bridge Link if active
                description=f"Add {format_currency(amount)} to wallet"
            )
            
            return {
                'success': True,
                'order_id': order_id,
                'payment_link': payment_link, # Bridge Link (if enabled)
                'raw_link': raw_link,         # Always the direct provider link
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
                # FALLBACK: Use environment-aware bridge
                env_tag = config.CASHFREE_ENV.upper()
                if "localhost" in config.DASHBOARD_URL:
                     if env_tag == "PRODUCTION":
                         payment_link = f"https://payments.cashfree.com/order/#{payment_session_id}"
                     else:
                         payment_link = f"https://sandbox.cashfree.com/pg/checkout/order/#{payment_session_id}"
                else:
                     payment_link = f"{config.DASHBOARD_URL.rstrip('/')}/pay/{env_tag}/{payment_session_id}"
                
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
                # FALLBACK: QR of environment-aware Bridge Link
                env_tag = config.CASHFREE_ENV.upper()
                qr_payload = f"{config.DASHBOARD_URL.rstrip('/')}/pay/{env_tag}/{payment_session_id}" if "localhost" not in config.DASHBOARD_URL else (
                    f"https://payments.cashfree.com/order/#{payment_session_id}" if env_tag == "PRODUCTION" else 
                    f"https://sandbox.cashfree.com/pg/checkout/order/#{payment_session_id}"
                )
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
