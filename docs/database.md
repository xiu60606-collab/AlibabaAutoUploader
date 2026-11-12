# SQLite 产品数据库（结构版本 1）

数据库使用内置 sqlite3，启动导入页时按 QStandardPaths.AppLocalDataLocation/products.sqlite3 初始化。应用名由 main.py 设置；不写入项目或 EXE 安装目录。
使用参数化 SQL、每连接启用外键、5 秒锁等待超时；批量导入 BEGIN IMMEDIATE，在整个批次成功后提交，异常回滚。
products 保存唯一文本 product_id、标题、文本 Decimal 价格、整数 MOQ 和来源批次；product_attributes 保存其余字段；product_images 保存图片路径、顺序、主图标志；import_batches 保存批次；import_errors 保存行号、字段和错误。
PRAGMA user_version 管理结构版本；当前支持新库到版本 1，拒绝打开更新版本，不会删除重建已有库。

## 重复处理

Excel 预览确认后如发现重复编号，提供跳过、更新、取消三个选择。取消不保存整个批次。更新必须在只读差异窗口再次确认；事务内重新核对差异，过期则拒绝更新。价格以文本写入，读回 Decimal。
删除产品会级联删除图片元数据和属性，不删除磁盘图片。

## 当前边界

Excel 导入已接入持久化，产品图片选择列表启动时加载数据库产品。原工作台/模拟表格保持模拟标识。
图片表提供原子 save_images 接口，图片面板的主图/顺序尚未自动写入数据库。
import_errors 提供 record_errors 接口，Excel 校验失败目前仍仅在界面显示，尚未自动保存错误历史。
读取 Excel 仍在后台；本次差异查询和数据库提交在主线程，大批量数据库提交的界面响应优化尚未完成。
单元测试使用独立临时目录，不读写生产数据库；Windows 实机与真实 macOS 桌面仍待验证。
