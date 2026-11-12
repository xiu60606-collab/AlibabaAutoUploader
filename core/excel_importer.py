"""只读 Excel 校验与原子内存提交。"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import logging
from pathlib import Path
from threading import Event
from openpyxl import load_workbook
from core.excel_template import FIELDS, REQUIRED

logger = logging.getLogger(__name__)
REQUIRED_IMPORT = REQUIRED | {'keywords', 'description'}
CURRENCIES = {'USD', 'CNY', 'EUR', 'GBP', 'JPY', 'HKD', 'AUD', 'CAD'}

@dataclass(frozen=True)
class ImportedProduct:
    row: int
    values: tuple[object, ...]

    @property
    def product_id(self) -> str:
        return str(self.values[0])

@dataclass(frozen=True)
class ImportResult:
    products: tuple[ImportedProduct, ...] = ()
    errors: tuple[str, ...] = ()

class MemoryProductStore:
    def __init__(self) -> None:
        self.products: tuple[ImportedProduct, ...] = ()

    def commit(self, result: ImportResult) -> None:
        """校验整批及已有编号冲突后一次性提交，不允许部分写入。"""
        if result.errors or not result.products:
            raise ValueError('第 1 行 [product_id]：没有可提交的完整批次')
        ids = {p.product_id for p in self.products}
        for product in result.products:
            if product.product_id in ids:
                raise ValueError(f'第 {product.row} 行 [product_id]：编号已存在')
            ids.add(product.product_id)
        self.products += result.products


def read_products(path: Path, cancel: Event | None = None) -> ImportResult:
    """流式读取第一张表；错误含原始行号，任何错误均禁止整批提交。"""
    path = Path(path)
    errors: list[str] = []
    products: list[ImportedProduct] = []
    seen: set[str] = set()
    def error(row: int, field: str, message: str) -> None:
        errors.append(f'第 {row} 行 [{field}]：{message}')
    if not path.is_file():
        return ImportResult(errors=('第 1 行 [file]：文件不存在或不是文件',))
    if path.suffix.lower() != '.xlsx':
        return ImportResult(errors=('第 1 行 [file]：仅支持 xlsx 文件',))
    try:
        wb = load_workbook(path, read_only=True, data_only=False)
        try:
            ws = wb.worksheets[0]
            rows = ws.iter_rows()
            headers = [str(c.value).strip() if c.value is not None else '' for c in next(rows, ())]
            for field in REQUIRED_IMPORT:
                if field not in headers:
                    error(1, field, '缺少必填列')
            for field in set(headers) - {''}:
                if headers.count(field) > 1:
                    error(1, field, '重复列名')
                elif field not in FIELDS:
                    error(1, field, '不支持的字段')
            if errors:
                return ImportResult(errors=tuple(errors))
            positions = {f: headers.index(f) for f in FIELDS if f in headers}
            for rownum, cells in enumerate(rows, 2):
                if cancel is not None and cancel.is_set():
                    return ImportResult(errors=(f'第 {rownum} 行 [file]：读取已取消',))
                if rownum > 100001:
                    error(rownum, 'file', '超过 100000 行读取上限，请拆分文件')
                    break
                if all(c.value is None or str(c.value).strip() == '' for c in cells):
                    continue
                before = len(errors)
                values: dict[str, object] = {}
                for field in FIELDS:
                    col = positions.get(field)
                    cell = cells[col] if col is not None and col < len(cells) else None
                    value = cell.value if cell is not None else None
                    if cell is not None and cell.data_type in {'f', 'e'}:
                        error(rownum, field, '不支持公式或 Excel 错误值')
                    if isinstance(value, bool):
                        error(rownum, field, '不支持布尔值')
                    text = '' if value is None else str(value).strip()
                    if field in REQUIRED_IMPORT and not text:
                        error(rownum, field, '不能为空')
                    if field == 'product_id':
                        if isinstance(value, (int, float)) and not isinstance(value, bool):
                            if Decimal(str(value)) != Decimal(str(value)).to_integral_value():
                                error(rownum, field, '数字编号必须为整数')
                            else:
                                text = str(int(value))
                                if cell and cell.number_format and set(cell.number_format) == {'0'}:
                                    text = text.zfill(len(cell.number_format))
                        if text in seen:
                            error(rownum, field, 'Excel 内编号重复')
                        seen.add(text)
                    if field in {'price', 'weight', 'moq'} and text:
                        try:
                            number = Decimal(text)
                            if not number.is_finite() or number < 0:
                                raise ValueError('须为有限非负数')
                            if field == 'moq' and (number <= 0 or number != number.to_integral_value()):
                                raise ValueError('MOQ 必须为正整数')
                            values[field] = int(number) if field == 'moq' else number
                        except (InvalidOperation, ValueError) as exc:
                            error(rownum, field, f'无效数字：{exc}')
                            values[field] = text
                    else:
                        values[field] = text
                    if field == 'currency' and text not in CURRENCIES:
                        error(rownum, field, '暂仅支持 ' + ', '.join(sorted(CURRENCIES)))
                if len(errors) == before:
                    products.append(ImportedProduct(rownum, tuple(values[f] for f in FIELDS)))
                if len(errors) >= 1000:
                    error(rownum, 'file', '错误过多，停止读取；请修正后重新读取')
                    break
        finally:
            wb.close()
    except Exception as exc:
        logger.exception('Excel 读取失败')
        error(1, 'file', f'无法打开或读取文件：{type(exc).__name__}: {exc}')
    return ImportResult(tuple(products), tuple(errors))
