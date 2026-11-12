"""SQLite 产品仓库：参数化语句、外键、原子导入及乐观差异校验。"""
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
import sqlite3
from core.excel_importer import ImportedProduct, ImportResult
from core.excel_template import FIELDS

SCHEMA_VERSION = 1


def application_database_path() -> Path:
    """解析用户可写数据目录；不创建或回退到安装目录。"""
    from PySide6.QtCore import QStandardPaths
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    if not location:
        raise RuntimeError('无法获取用户应用数据目录')
    return Path(location) / 'products.sqlite3'


class ProductDatabase:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version > SCHEMA_VERSION:
                raise ValueError('数据库结构版本过新，拒绝修改')
            if version == 0:
                statements = [
                    'CREATE TABLE import_batches (id INTEGER PRIMARY KEY, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, policy TEXT NOT NULL, product_count INTEGER NOT NULL)',
                    'CREATE TABLE products (product_id TEXT PRIMARY KEY NOT NULL CHECK(length(product_id)>0), title TEXT NOT NULL, price TEXT NOT NULL, moq INTEGER NOT NULL CHECK(moq>0), batch_id INTEGER REFERENCES import_batches(id) ON DELETE SET NULL)',
                    'CREATE TABLE product_attributes (product_id TEXT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE, name TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(product_id,name))',
                    'CREATE TABLE product_images (id INTEGER PRIMARY KEY, product_id TEXT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE, path TEXT NOT NULL, position INTEGER NOT NULL CHECK(position>=0), is_main INTEGER NOT NULL CHECK(is_main IN (0,1)), UNIQUE(product_id,path), UNIQUE(product_id,position))',
                    'CREATE UNIQUE INDEX one_main_image ON product_images(product_id) WHERE is_main=1',
                    'CREATE TABLE import_errors (id INTEGER PRIMARY KEY, batch_id INTEGER NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE, excel_row INTEGER NOT NULL, field TEXT NOT NULL, message TEXT NOT NULL)',
                ]
                for statement in statements:
                    db.execute(statement)
                db.execute('PRAGMA user_version=1')

    @contextmanager
    def connection(self):
        """每次操作独立连接，异常自动回滚并向调用者传播。"""
        db = sqlite3.connect(self.path, timeout=5)
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def _get(self, db, product_id: str) -> ImportedProduct | None:
        row = db.execute('SELECT product_id,title,price,moq FROM products WHERE product_id=?',(product_id,)).fetchone()
        if row is None:return None
        values = dict(db.execute('SELECT name,value FROM product_attributes WHERE product_id=?',(product_id,)))
        values.update(product_id=row[0],title=row[1],price=Decimal(row[2]),moq=row[3])
        if values.get('weight'):values['weight']=Decimal(values['weight'])
        return ImportedProduct(0,tuple(values.get(f,'') for f in FIELDS))

    def get(self, product_id: str) -> ImportedProduct | None:
        with self.connection() as db:return self._get(db,product_id)

    @property
    def products(self) -> tuple[ImportedProduct,...]:
        with self.connection() as db:
            return tuple(self._get(db,row[0]) for row in db.execute('SELECT product_id FROM products ORDER BY product_id').fetchall())

    def differences(self, result: ImportResult) -> dict:
        """返回每个重复编号所有字段的旧值/新值，含未发生变化的重复项。"""
        with self.connection() as db:return self._differences(db,result)

    def _differences(self, db, result: ImportResult) -> dict:
        differences={}
        for p in result.products:
            old=self._get(db,p.product_id)
            if old is not None:
                differences[p.product_id]={f:(str(a),str(b)) for f,a,b in zip(FIELDS,old.values,p.values) if a!=b}
        return differences

    def _write(self, db, product: ImportedProduct, batch: int, update: bool) -> None:
        data=dict(zip(FIELDS,product.values))
        if len(product.values)!=len(FIELDS) or not product.product_id.strip():raise ValueError('无效产品字段')
        if not isinstance(data['price'],Decimal) or not data['price'].is_finite() or data['price']<0:raise ValueError('无效价格')
        if type(data['moq']) is not int or data['moq']<=0:raise ValueError('无效 MOQ')
        if update:
            db.execute('UPDATE products SET title=?,price=?,moq=?,batch_id=? WHERE product_id=?',(data['title'],str(data['price']),data['moq'],batch,product.product_id))
            db.execute('DELETE FROM product_attributes WHERE product_id=?',(product.product_id,))
        else:
            db.execute('INSERT INTO products(product_id,title,price,moq,batch_id) VALUES(?,?,?,?,?)',(product.product_id,data['title'],str(data['price']),data['moq'],batch))
        db.executemany('INSERT INTO product_attributes(product_id,name,value) VALUES(?,?,?)',[(product.product_id,f,str(data[f])) for f in FIELDS if f not in {'product_id','title','price','moq'}])

    def import_products(self, result: ImportResult, policy: str='cancel', approved_diff: dict | None=None) -> int:
        """重复时默认取消整批；更新必须携带已向用户展示并确认的差异。"""
        if policy not in {'cancel','skip','update'}:raise ValueError('未知重复处理方式')
        if result.errors or not result.products:raise ValueError('导入批次存在错误或为空')
        ids=[p.product_id for p in result.products]
        if len(set(ids))!=len(ids):raise ValueError('批次内产品编号重复')
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            diff=self._differences(db,result)
            if diff and policy=='cancel':raise ValueError('发现重复产品，导入已取消')
            if diff and policy=='update' and approved_diff!=diff:raise ValueError('请重新预览并确认差异，数据可能已变化')
            batch=db.execute('INSERT INTO import_batches(policy,product_count) VALUES(?,0)',(policy,)).lastrowid
            count=0
            for product in result.products:
                exists=product.product_id in diff
                if exists and policy=='skip':continue
                self._write(db,product,batch,exists)
                count+=1
            db.execute('UPDATE import_batches SET product_count=? WHERE id=?',(count,batch))
            return count

    def commit(self,result: ImportResult) -> None:
        self.import_products(result)

    def add(self,product: ImportedProduct) -> None:
        self.commit(ImportResult((product,)))

    def update(self,product: ImportedProduct,approved_diff: dict) -> None:
        if self.get(product.product_id) is None:raise KeyError(product.product_id)
        self.import_products(ImportResult((product,)),'update',approved_diff)

    def delete(self,product_id: str) -> None:
        with self.connection() as db:db.execute('DELETE FROM products WHERE product_id=?',(product_id,))

    def save_images(self,product_id: str,images: list[tuple[str,bool]]) -> None:
        """原子替换图片路径及排序元数据，不写入原始图片。"""
        with self.connection() as db:
            db.execute('DELETE FROM product_images WHERE product_id=?',(product_id,))
            db.executemany('INSERT INTO product_images(product_id,path,position,is_main) VALUES(?,?,?,?)',[(product_id,path,i,int(main)) for i,(path,main) in enumerate(images)])

    def record_errors(self,errors: list[tuple[int,str,str]]) -> int:
        with self.connection() as db:
            batch=db.execute("INSERT INTO import_batches(policy,product_count) VALUES('validation_failed',0)").lastrowid
            db.executemany('INSERT INTO import_errors(batch_id,excel_row,field,message) VALUES(?,?,?,?)',[(batch,*e) for e in errors])
            return batch

    def get_images(self,product_id: str) -> list[tuple[str,bool]]:
        with self.connection() as db:
            return [(p,bool(m)) for p,m in db.execute('SELECT path,is_main FROM product_images WHERE product_id=? ORDER BY position',(product_id,))]

    def save_edit(self,original: ImportedProduct,edited: ImportedProduct,root: Path,images: list[tuple[str,bool]]) -> None:
        """重校验并原子提交资料及图片；并发修改或任一写入错误整批回滚。"""
        from core.product_validation import ProductValidator
        if original.product_id!=edited.product_id:raise ValueError('不允许修改产品编号')
        errors=ProductValidator().validate(edited,root,[p for p,_ in images])
        if not images:errors.append('images：至少需要一张图片')
        if sum(bool(m) for _,m in images)!=1:errors.append('images：必须指定且仅指定一张主图')
        if errors:raise ValueError('\n'.join(errors))
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            current=self._get(db,original.product_id)
            if current is None or current.values!=original.values:raise ValueError('产品已被修改或删除，请重新加载')
            batch=db.execute("INSERT INTO import_batches(policy,product_count) VALUES('edit',1)").lastrowid
            self._write(db,edited,batch,True)
            db.execute('DELETE FROM product_images WHERE product_id=?',(edited.product_id,))
            db.executemany('INSERT INTO product_images(product_id,path,position,is_main) VALUES(?,?,?,?)',[(edited.product_id,p,i,int(m)) for i,(p,m) in enumerate(images)])
