"""可扩展本地通用规则，不是阿里巴巴官方完整发布规则。"""
from decimal import Decimal, InvalidOperation
from pathlib import Path
from collections.abc import Callable
from core.excel_template import FIELDS
from core.excel_importer import ImportedProduct, REQUIRED_IMPORT
from core.product_images import scan_images

Rule = Callable[[dict], list[str]]

def required_rule(data: dict) -> list[str]:
    return [f'{field}：必填字段不能为空' for field in sorted(REQUIRED_IMPORT) if not str(data.get(field,'')).strip()]

def numeric_rule(data: dict) -> list[str]:
    errors=[]
    for field in ('price','moq'):
        try:
            if isinstance(data.get(field),bool):raise ValueError()
            value=Decimal(str(data.get(field,'')))
            if not value.is_finite() or value<=0 or (field=='moq' and value!=value.to_integral_value()):raise ValueError()
        except (InvalidOperation,ValueError):errors.append(f'{field}：须为正数' if field=='price' else 'moq：须为正整数')
    return errors

class ProductValidator:
    def __init__(self, extra_rules: tuple[Rule,...]=()) -> None:
        self.rules=(required_rule,numeric_rule,*extra_rules)

    def validate(self,product: ImportedProduct,root: Path | None, image_paths: list[str] | None=None) -> list[str]:
        """重读原图而不信任缩略图缓存；可注入类目专用字段规则。"""
        data=dict(zip(FIELDS,product.values))
        errors=[e for rule in self.rules for e in rule(data)]
        if root is None:return errors+['image_folder：请选择图片根目录']
        collection=scan_images(root,str(data.get('image_folder','')))
        errors.extend('images：'+e for e in collection.errors)
        if image_paths is not None:
            found={str(i.path) for i in collection.images}
            for path in image_paths:
                if path not in found:errors.append(f'images：图片不存在、失效或不属于产品目录：{path}')
            if len(set(image_paths))!=len(image_paths):errors.append('images：图片重复')
        return errors

    def validate_all(self,products: tuple[ImportedProduct,...],root: Path | None) -> dict[str,list[str]]:
        result={};seen=set()
        for product in products:
            errors=self.validate(product,root)
            if product.product_id in seen:errors.append('product_id：重复编号')
            seen.add(product.product_id)
            result.setdefault(product.product_id,[]).extend(errors)
        return result
