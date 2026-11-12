"""仅用于界面展示的模拟产品，不代表真实上传结果。"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Product:
    """产品列表的只读展示数据。"""
    number: str
    title: str
    price: str
    images: int
    status: str
    updated: str

DEMO_PRODUCTS = (
    Product("DEMO-001", "便携式不锈钢保温杯", "USD 8.50", 5, "待上传（模拟）", "—"),
    Product("DEMO-002", "商务办公桌面收纳盒", "USD 12.00", 4, "待上传（模拟）", "—"),
    Product("DEMO-003", "可折叠户外旅行背包", "USD 18.90", 6, "待上传（模拟）", "—"),
)
