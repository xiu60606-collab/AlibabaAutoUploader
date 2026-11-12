"""模板生成与 Excel 回读测试。"""
import pytest
from openpyxl import load_workbook
from core.excel_template import generate_template, FIELDS, REQUIRED

def test_template_roundtrip(tmp_path):
    path = generate_template(tmp_path / "template.xlsx")
    wb = load_workbook(path)
    try:
        ws = wb["products"]
        assert tuple(c.value for c in ws[1]) == FIELDS
        assert ws.max_row == 4
        assert len({ws.cell(r,1).value for r in range(2,5)}) == 3
        for row in range(2,5):
            assert ws.cell(row,1).data_type == "s"
            assert ws.cell(row,1).value == f"{row-1:06d}"
            assert ws.cell(row,1).number_format == "@"
            assert isinstance(ws.cell(row,6).value,(int,float))
            assert ws.cell(row,6).number_format == "0.00"
            assert ws.cell(row,8).number_format == "0"
            assert ws.cell(row,12).number_format == "0.000"
        assert ws.freeze_panes == "A2"
        assert len(ws.data_validations.dataValidation) == 13
        for cell in ws[1]:
            assert "示例" in cell.comment.text
            if cell.value in REQUIRED:
                assert "必填" in cell.comment.text
        id_rule = ws.data_validations.dataValidation[0]
        assert "COUNTIF" in id_rule.formula1 and "ISTEXT" in id_rule.formula1
        assert not id_rule.allow_blank
    finally:
        wb.close()
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        generate_template(path)
    assert path.read_bytes() == before

def test_reject_non_xlsx(tmp_path):
    with pytest.raises(ValueError):
        generate_template(tmp_path / "bad.csv")
