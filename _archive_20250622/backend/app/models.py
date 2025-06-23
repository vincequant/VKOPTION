from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
import os

# 数据库配置
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/ib_monitor")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class PositionHistory(Base):
    """仓位历史记录表"""
    __tablename__ = "position_history"

    id = Column(Integer, primary_key=True, index=True)
    account = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    contract_id = Column(Integer, nullable=False)
    position = Column(Float, nullable=False)
    market_price = Column(Float, nullable=False)
    market_value = Column(Float, nullable=False)
    avg_cost = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, nullable=False)
    realized_pnl = Column(Float, nullable=False)
    currency = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AccountHistory(Base):
    """账户历史记录表"""
    __tablename__ = "account_history"

    id = Column(Integer, primary_key=True, index=True)
    account = Column(String, nullable=False)
    total_cash_value = Column(Float, nullable=False)
    net_liquidation = Column(Float, nullable=False)
    gross_position_value = Column(Float, nullable=False)
    buying_power = Column(Float, nullable=False)
    currency = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# 创建数据库表
def create_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()