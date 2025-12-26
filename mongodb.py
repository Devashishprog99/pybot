"""
MongoDB Database Module for Gmail Marketplace Bot
"""
from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime
from typing import Optional, List, Dict
import config

class MongoDatabase:
    def __init__(self):
        self.client = MongoClient(config.MONGODB_URI)
        self.db = self.client[config.DATABASE_NAME]
        
        # Collections
        self.users = self.db.users
        self.sellers = self.db.sellers
        self.gmails = self.db.gmails
        self.transactions = self.db.transactions
        self.withdrawals = self.db.withdrawals
        self.support_messages = self.db.support_messages
        
        # Create indexes
        self.create_indexes()
    
    def create_indexes(self):
        """Create database indexes for performance"""
        self.users.create_index([("user_id", ASCENDING)], unique=True)
        self.sellers.create_index([("user_id", ASCENDING)])
        self.sellers.create_index([("status", ASCENDING)])
        self.gmails.create_index([("status", ASCENDING)])
        self.gmails.create_index([("batch_id", ASCENDING)])
        self.gmails.create_index([("seller_id", ASCENDING)])
        self.transactions.create_index([("user_id", ASCENDING)])
        self.transactions.create_index([("cashfree_order_id", ASCENDING)])
        self.withdrawals.create_index([("seller_id", ASCENDING)])
        self.withdrawals.create_index([("status", ASCENDING)])
    
    # ==================== USER OPERATIONS ====================
    
    def create_user(self, user_id: int, username: str, full_name: str) -> bool:
        """Create or update user"""
        try:
            self.users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "username": username,
                    "full_name": full_name,
                    "updated_at": datetime.now()
                }, "$setOnInsert": {
                    "wallet_balance": 0.0,
                    "role": "buyer",
                    "is_banned": False,
                    "created_at": datetime.now()
                }},
                upsert=True
            )
            return True
        except Exception as e:
            print(f"Error creating user: {e}")
            return False
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        return self.users.find_one({"user_id": user_id})
    
    def update_wallet(self, user_id: int, amount: float) -> bool:
        """Update user wallet balance"""
        try:
            result = self.users.update_one(
                {"user_id": user_id},
                {"$inc": {"wallet_balance": amount}}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"Error updating wallet: {e}")
            return False
    
    def get_wallet_balance(self, user_id: int) -> float:
        """Get user wallet balance"""
        user = self.users.find_one({"user_id": user_id}, {"wallet_balance": 1})
        return user.get("wallet_balance", 0.0) if user else 0.0
    
    def ban_user(self, user_id: int, banned: bool = True) -> bool:
        """Ban or unban user"""
        result = self.users.update_one(
            {"user_id": user_id},
            {"$set": {"is_banned": banned}}
        )
        return result.modified_count > 0
    
    # ==================== SELLER OPERATIONS ====================
    
    def create_seller(self, user_id: int, upi_qr_path: str) -> bool:
        """Register user as seller"""
        try:
            self.sellers.insert_one({
                "user_id": user_id,
                "upi_qr_path": upi_qr_path,
                "status": "pending",
                "total_earnings": 0.0,
                "created_at": datetime.now()
            })
            
            # Update user role
            self.users.update_one(
                {"user_id": user_id},
                {"$set": {"role": "seller"}}
            )
            return True
        except Exception as e:
            print(f"Error creating seller: {e}")
            return False
    
    def get_seller(self, user_id: int) -> Optional[Dict]:
        """Get seller by user ID"""
        return self.sellers.find_one({"user_id": user_id})
    
    def get_seller_by_id(self, seller_id) -> Optional[Dict]:
        """Get seller by seller ID"""
        from bson import ObjectId
        seller = self.sellers.find_one({"_id": ObjectId(seller_id)})
        if seller:
            user = self.users.find_one({"user_id": seller["user_id"]})
            seller["username"] = user.get("username", "Unknown") if user else "Unknown"
            seller["full_name"] = user.get("full_name", "") if user else ""
            seller["seller_id"] = str(seller["_id"])
        return seller
    
    def approve_seller(self, seller_id, admin_id: int, approved: bool = True) -> bool:
        """Approve or reject seller"""
        from bson import ObjectId
        status = 'approved' if approved else 'rejected'
        result = self.sellers.update_one(
            {"_id": ObjectId(seller_id)},
            {"$set": {
                "status": status,
                "approved_at": datetime.now(),
                "approved_by": admin_id
            }}
        )
        return result.modified_count > 0
    
    def get_pending_sellers(self) -> List[Dict]:
        """Get all pending sellers"""
        sellers = list(self.sellers.find({"status": "pending"}).sort("created_at", ASCENDING))
        for seller in sellers:
            user = self.users.find_one({"user_id": seller["user_id"]})
            seller["username"] = user.get("username", "Unknown") if user else "Unknown"
            seller["full_name"] = user.get("full_name", "") if user else ""
            seller["seller_id"] = str(seller["_id"])
        return sellers
    
    def get_all_sellers_with_stats(self) -> List[Dict]:
        """Get all sellers with their Gmail statistics"""
        pipeline = [
            {
                "$lookup": {
                    "from": "users",
                    "localField": "user_id",
                    "foreignField": "user_id",
                    "as": "user_info"
                }
            },
            {
                "$lookup": {
                    "from": "gmails",
                    "let": {"seller_id": "$_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$seller_id", {"$toString": "$$seller_id"}]}}}
                    ],
                    "as": "gmails"
                }
            },
            {
                "$project": {
                    "user_id": 1,
                    "status": 1,
                    "total_earnings": 1,
                    "username": {"$arrayElemAt": ["$user_info.username", 0]},
                    "full_name": {"$arrayElemAt": ["$user_info.full_name", 0]},
                    "pending_gmails": {
                        "$size": {
                            "$filter": {
                                "input": "$gmails",
                                "cond": {"$eq": ["$$this.status", "pending"]}
                            }
                        }
                    },
                    "available_gmails": {
                        "$size": {
                            "$filter": {
                                "input": "$gmails",
                                "cond": {"$eq": ["$$this.status", "available"]}
                            }
                        }
                    },
                    "sold_gmails": {
                        "$size": {
                            "$filter": {
                                "input": "$gmails",
                                "cond": {"$eq": ["$$this.status", "sold"]}
                            }
                        }
                    }
                }
            },
            {"$sort": {"status": 1, "created_at": -1}}
        ]
        
        return list(self.sellers.aggregate(pipeline))
    
    def update_seller_earnings(self, seller_id, amount: float) -> bool:
        """Update seller earnings"""
        from bson import ObjectId
        result = self.sellers.update_one(
            {"_id": ObjectId(seller_id)},
            {"$inc": {"total_earnings": amount}}
        )
        return result.modified_count > 0
    
    # ==================== GMAIL OPERATIONS ====================
    
    def add_gmails(self, seller_id: str, gmails: List[tuple], batch_id: str) -> bool:
        """Add Gmail accounts for sale"""
        try:
            docs = []
            for email, password in gmails:
                docs.append({
                    "seller_id": seller_id,
                    "email": email,
                    "password": password,
                    "batch_id": batch_id,
                    "status": "pending",
                    "created_at": datetime.now()
                })
            self.gmails.insert_many(docs)
            return True
        except Exception as e:
            print(f"Error adding Gmails: {e}")
            return False
    
    def approve_gmail_batch(self, batch_id: str, approved: bool = True) -> bool:
        """Approve or reject Gmail batch"""
        status = 'available' if approved else 'rejected'
        result = self.gmails.update_many(
            {"batch_id": batch_id, "status": "pending"},
            {"$set": {
                "status": status,
                "approved_at": datetime.now()
            }}
        )
        return result.modified_count > 0
    
    def get_available_gmails_count(self) -> int:
        """Get count of available Gmails"""
        return self.gmails.count_documents({"status": "available"})
    
    def purchase_gmails(self, buyer_id: int, quantity: int) -> List[Dict]:
        """Purchase Gmail accounts"""
        try:
            # Get available Gmails
            gmails = list(self.gmails.find({"status": "available"}).limit(quantity))
            
            if len(gmails) < quantity:
                return []
            
            # Mark as sold
            gmail_ids = [g["_id"] for g in gmails]
            self.gmails.update_many(
                {"_id": {"$in": gmail_ids}},
                {"$set": {
                    "status": "sold",
                    "buyer_id": buyer_id,
                    "sold_at": datetime.now()
                }}
            )
            
            return gmails
        except Exception as e:
            print(f"Error purchasing Gmails: {e}")
            return []
    
    def get_pending_gmail_batches(self) -> List[Dict]:
        """Get pending Gmail batches"""
        pipeline = [
            {"$match": {"status": "pending"}},
            {
                "$group": {
                    "_id": "$batch_id",
                    "count": {"$sum": 1},
                    "seller_id": {"$first": "$seller_id"},
                    "created_at": {"$min": "$created_at"},
                    "sample_emails": {"$push": "$email"}
                }
            },
            {
                "$project": {
                    "batch_id": "$_id",
                    "count": 1,
                    "seller_id": 1,
                    "created_at": 1,
                    "sample_emails": {"$slice": ["$sample_emails", 3]}
                }
            },
            {"$sort": {"created_at": 1}}
        ]
        
        batches = list(self.gmails.aggregate(pipeline))
        for batch in batches:
            batch["batch_id"] = batch["_id"]
            batch["sample_emails"] = ", ".join(batch["sample_emails"])
            # Get seller info
            from bson import ObjectId
            seller = self.sellers.find_one({"_id": ObjectId(batch["seller_id"])})
            if seller:
                user = self.users.find_one({"user_id": seller["user_id"]})
                batch["username"] = user.get("username", "Unknown") if user else "Unknown"
                batch["user_id"] = seller["user_id"]
        
        return batches
    
    def get_user_purchases(self, user_id: int) -> List[Dict]:
        """Get user's purchased Gmails"""
        return list(self.gmails.find({"buyer_id": user_id, "status": "sold"}).sort("sold_at", DESCENDING))
    
    def get_seller_sales(self, seller_id: str) -> Dict:
        """Get seller's sales statistics"""
        from bson import ObjectId
        total_sold = self.gmails.count_documents({"seller_id": str(seller_id), "status": "sold"})
        total_available = self.gmails.count_documents({"seller_id": str(seller_id), "status": "available"})
        total_pending = self.gmails.count_documents({"seller_id": str(seller_id), "status": "pending"})
        
        return {
            "sold_count": total_sold,
            "available_count": total_available,
            "pending_count": total_pending
        }
    
    # ==================== TRANSACTION OPERATIONS ====================
    
    def create_transaction(self, user_id: int, txn_type: str, amount: float, 
                          cashfree_order_id: str = None, payment_link: str = None,
                          description: str = None) -> str:
        """Create transaction record"""
        result = self.transactions.insert_one({
            "user_id": user_id,
            "type": txn_type,
            "amount": amount,
            "cashfree_order_id": cashfree_order_id,
            "payment_link": payment_link,
            "description": description,
            "status": "pending",
            "created_at": datetime.now()
        })
        return str(result.inserted_id)
    
    def update_transaction_status(self, txn_id: str, status: str) -> bool:
        """Update transaction status"""
        from bson import ObjectId
        result = self.transactions.update_one(
            {"_id": ObjectId(txn_id)},
            {"$set": {
                "status": status,
                "completed_at": datetime.now()
            }}
        )
        return result.modified_count > 0
    
    def get_transaction_by_order_id(self, order_id: str) -> Optional[Dict]:
        """Get transaction by Cashfree order ID"""
        txn = self.transactions.find_one({"cashfree_order_id": order_id})
        if txn:
            txn["txn_id"] = str(txn["_id"])
        return txn
    
    def get_user_transactions(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get user transaction history"""
        return list(self.transactions.find({"user_id": user_id}).sort("created_at", DESCENDING).limit(limit))
    
    # ==================== WITHDRAWAL OPERATIONS ====================
    
    def create_withdrawal(self, seller_id: str, user_id: int, amount: float, upi_qr_path: str) -> str:
        """Create withdrawal request"""
        result = self.withdrawals.insert_one({
            "seller_id": seller_id,
            "user_id": user_id,
            "amount": amount,
            "upi_qr_path": upi_qr_path,
            "status": "pending",
            "created_at": datetime.now()
        })
        return str(result.inserted_id)
    
    def get_pending_withdrawals(self) -> List[Dict]:
        """Get all pending withdrawal requests"""
        withdrawals = list(self.withdrawals.find({"status": "pending"}).sort("created_at", ASCENDING))
        for withdrawal in withdrawals:
            withdrawal["withdrawal_id"] = str(withdrawal["_id"])
            user = self.users.find_one({"user_id": withdrawal["user_id"]})
            if user:
                withdrawal["username"] = user.get("username", "Unknown")
                withdrawal["full_name"] = user.get("full_name", "") 
            from bson import ObjectId
            seller = self.sellers.find_one({"_id": ObjectId(withdrawal["seller_id"])})
            if seller:
                withdrawal["total_earnings"] = seller.get("total_earnings", 0.0)
        return withdrawals
    
    def get_pending_withdrawals_with_sales(self) -> List[Dict]:
        """Get pending withdrawals only from sellers who have sold Gmails"""
        withdrawals = self.get_pending_withdrawals()
        filtered = []
        for w in withdrawals:
            sold_count = self.gmails.count_documents({"seller_id": w["seller_id"], "status": "sold"})
            if sold_count > 0:
                w["total_sold"] = sold_count
                filtered.append(w)
        return filtered
    
    def process_withdrawal(self, withdrawal_id: str, admin_id: int, approved: bool = True) -> bool:
        """Process withdrawal request"""
        from bson import ObjectId
        status = 'paid' if approved else 'rejected'
        result = self.withdrawals.update_one(
            {"_id": ObjectId(withdrawal_id)},
            {"$set": {
                "status": status,
                "processed_at": datetime.now(),
                "processed_by": admin_id
            }}
        )
        return result.modified_count > 0
    
    # ==================== STATISTICS ====================
    
    def get_stats(self) -> Dict:
        """Get system statistics"""
        stats = {}
        
        stats['total_users'] = self.users.count_documents({})
        stats['available_gmails'] = self.gmails.count_documents({"status": "available"})
        stats['sold_gmails'] = self.gmails.count_documents({"status": "sold"})
        stats['pending_sellers'] = self.sellers.count_documents({"status": "pending"})
        
        # Count distinct pending batches
        pending_batches = self.gmails.distinct("batch_id", {"status": "pending"})
        stats['pending_batches'] = len(pending_batches)
        
        stats['pending_withdrawals'] = self.withdrawals.count_documents({"status": "pending"})
        
        # Calculate revenue (wallet loads + purchases)
        revenue_pipeline = [
            {"$match": {"status": "success"}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        revenue_result = list(self.transactions.aggregate(revenue_pipeline))
        stats['total_revenue'] = revenue_result[0]["total"] if revenue_result else 0.0
        
        # Seller pending amount (sum of total_earnings for all approved/pending sellers who haven't withdrawn)
        pending_payout_pipeline = [
            {"$group": {"_id": None, "total": {"$sum": "$total_earnings"}}}
        ]
        payout_result = list(self.sellers.aggregate(pending_payout_pipeline))
        stats['seller_pending_payouts'] = payout_result[0]["total"] if payout_result else 0.0
        
        return stats

    def get_time_based_analytics(self) -> Dict:
        """Get daily, weekly, monthly, and yearly transaction analytics"""
        analytics = {}
        now = datetime.now()
        
        # Ranges
        ranges = {
            'daily': now - timedelta(days=1),
            'weekly': now - timedelta(days=7),
            'monthly': now - timedelta(days=30),
            'yearly': now - timedelta(days=365)
        }
        
        for label, start_date in ranges.items():
            pipeline = [
                {"$match": {"status": "success", "created_at": {"$gte": start_date}}},
                {"$group": {
                    "_id": None, 
                    "total_amount": {"$sum": "$amount"},
                    "count": {"$sum": 1}
                }}
            ]
            result = list(self.transactions.aggregate(pipeline))
            analytics[label] = result[0] if result else {"total_amount": 0, "count": 0}
            
        return analytics

    def save_support_message(self, user_id: int, message: str) -> bool:
        """Save support message from user"""
        try:
            self.support_messages.insert_one({
                "user_id": user_id,
                "message": message,
                "status": "unread",
                "created_at": datetime.now()
            })
            return True
        except Exception as e:
            print(f"Error saving support message: {e}")
            return False

    def get_support_messages(self, unread_only: bool = True) -> List[Dict]:
        """Get support messages for admin"""
        query = {"status": "unread"} if unread_only else {}
        messages = list(self.support_messages.find(query).sort("created_at", DESCENDING))
        for msg in messages:
            msg["_id"] = str(msg["_id"])
            user = self.get_user(msg["user_id"])
            msg["username"] = user.get("username", "Unknown") if user else "Unknown"
        return messages

# Global database instance
db = MongoDatabase()
