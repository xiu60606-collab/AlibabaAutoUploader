"""生成产品导入模板；不读取真实产品或连接客户端。"""
import logging
from pathlib import Path
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)
FIELDS = ("product_id", "title", "keywords", "description", "category", "price", "currency", "moq", "material", "color", "size", "weight", "image_folder")
REQUIRED = {"product_id", "title", "category", "price", "currency", "moq", "image_folder"}
EXAMPLES = (
    ("000001", "Fictional Travel Cup", "cup; travel", "Fictional example only", "Home / Drinkware", 8.50, "USD", 100, "Stainless steel", "Blue", "500 ml", 0.35, "images/000001"),
    ("000002", "Fictional Storage Box", "box; office", "Fictional example only", "Office / Storage", 12.00, "USD", 50, "Plastic", "White", "30 x 20 x 10 cm", 0.60, "images/000002"),
    ("000003", "Fictional Travel Bag", "bag; travel", "Fictional example only", "Bags / Travel", 18.90, "USD", 20, "Polyester", "Black", "20 L", 0.75, "images/000003"),
)

def generate_template(destination: Path) -> Path:
    """创建不超过 10000 行的填写模板，拒绝覆盖已有文件。"""
    destination = Path(destination)
    if destination.suffix.lower() != ".xlsx":
        raise ValueError("模板必须使用 .xlsx 扩展名")
    destination.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "products"
    ws.append(FIELDS)
    for row in EXAMPLES:
        ws.append(row)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = "A1:M4"
    for col, field in enumerate(FIELDS, 1):
        letter = get_column_letter(col)
        header = ws.cell(1, col)
        required = field in REQUIRED
        header.font = Font(bold=True, color="FFFFFF")
        header.fill = PatternFill("solid", fgColor="B45309" if required else "24476A")
        header.comment = Comment(f"{'必填' if required else '选填'}；示例：{EXAMPLES[0][col-1]}" + ("；文本，保留前导零且全表唯一" if field == "product_id" else ""), "Template")
        ws.column_dimensions[letter].width = 42 if field in {"title", "description", "image_folder"} else 22
        fmt = "0.00" if field == "price" else "0.000" if field == "weight" else "0" if field == "moq" else "@"
        ws.column_dimensions[letter].number_format = fmt
        for row in range(2, 5):
            cell = ws.cell(row, col)
            cell.number_format = fmt
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        if field == "product_id":
            formula = 'AND(ISTEXT(A2),LEN(TRIM(A2))>0,COUNTIF($A$2:$A$10000,A2)=1)'
            validation = DataValidation(type="custom", formula1=formula, allow_blank=False)
        elif field in {"price", "weight", "moq"}:
            validation = DataValidation(type="whole" if field == "moq" else "decimal", operator="greaterThan" if field == "moq" else "greaterThanOrEqual", formula1=0, allow_blank=not required)
        else:
            validation = DataValidation(type="custom", formula1=f'LEN(TRIM({letter}2))>0' if required else 'TRUE', allow_blank=not required)
        validation.showInputMessage = True
        validation.promptTitle = "必填字段" if required else "选填字段"
        validation.prompt = f"示例：{EXAMPLES[0][col-1]}"
        validation.showErrorMessage = True
        validation.errorTitle = "字段填写有误"
        validation.error = "请参考字段说明；编号须为唯一文本，数字须符合范围。"
        validation.errorStyle = "stop"
        ws.add_data_validation(validation)
        validation.add(f"{letter}2:{letter}10000")
    ws.row_dimensions[1].height = 30
    for row in range(2, 5):
        ws.row_dimensions[row].height = 42
    try:
        with destination.open("xb") as stream:
            wb.save(stream)
    finally:
        wb.close()
    logger.info("已生成虚构示例产品模板：%s", destination)
    return destination
