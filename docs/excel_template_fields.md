# Excel 产品模板字段说明（v0.3.0）

第一行为英文机器字段名，第二行开始一行一个产品。三条记录均为虚构示例，使用前请删除或替换。橙色表头为必填，蓝色为选填；表头批注和选中单元格提示提供填写示例。

| 字段 | 必填 | 类型 / 约定 | 示例 |
| --- | --- | --- | --- |
| product_id | 是 | 唯一文本，不可重复；输入前设为文本，保留前导零 | 000001 |
| title | 是 | 文本 | Fictional Travel Cup |
| keywords | 否 | 文本，多个关键词以英文分号分隔 | cup; travel |
| description | 否 | 文本 | Fictional example only |
| category | 是 | 文本，示例类目路径不代表平台真实类目 | Home / Drinkware |
| price | 是 | 非负数，显示两位小数 | 8.5 |
| currency | 是 | 三位大写币种代码，例如 USD；本阶段不提供完整币种校验 | USD |
| moq | 是 | 正整数，起订量 | 100 |
| material | 否 | 文本 | Stainless steel |
| color | 否 | 文本 | Blue |
| size | 否 | 文本 | 500 ml |
| weight | 否 | 非负数，单位 kg，显示三位小数 | 0.35 |
| image_folder | 是 | 图片目录，相对路径约定相对于产品表文件；示例目录不实际存在 | images/000001 |

模板对第 2–10000 行设置提示和校验。数字样式采用 0.00（价格）、0（起订量）、0.000（重量），其他字段为文本。

Excel 数据验证可被粘贴、删除等操作绕过，空白产品行也不会被自动判为错误；不能替代后续导入器的必填、唯一性、币种和路径校验。本阶段不实现导入器或读取图片目录。已被 Excel 转换丢失的前导零无法靠格式恢复。

生成方法（目标已存在时拒绝覆盖）：

```python
from pathlib import Path
from core.excel_template import generate_template
generate_template(Path("templates/new_product_template.xlsx"))
```

本阶段未更改主界面版本标识。Windows Excel 实际交互验证尚未执行。
