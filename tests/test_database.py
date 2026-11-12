"""数据库 CRUD、重复策略、回滚、外键与结构版本。"""
from dataclasses import replace
from decimal import Decimal
import sqlite3
import pytest
from core.database import ProductDatabase
from core.excel_importer import ImportResult
from core.excel_template import generate_template
from core.excel_importer import read_products

@pytest.fixture
def batch(tmp_path):
    return read_products(generate_template(tmp_path/'input.xlsx'))


def test_crud_persistence_and_duplicate(tmp_path,batch):
    path=tmp_path/'db.sqlite3';db=ProductDatabase(path)
    p=batch.products[0];db.add(p)
    assert db.get('000001').values==p.values
    with pytest.raises(ValueError):db.add(p)
    changed=replace(p,values=tuple('New title' if i==1 else v for i,v in enumerate(p.values)))
    diff=db.differences(ImportResult((changed,)))
    assert diff['000001']['title']==('Fictional Travel Cup','New title')
    with pytest.raises(ValueError):db.update(changed,{})
    db.update(changed,diff)
    assert ProductDatabase(path).get('000001').values[1]=='New title'
    db.delete('000001');assert db.get('000001') is None


def test_batch_policies_and_atomic_rollback(tmp_path,batch):
    db=ProductDatabase(tmp_path/'db')
    db.add(batch.products[0])
    with pytest.raises(ValueError):db.import_products(batch)
    assert len(db.products)==1
    assert db.import_products(batch,'skip')==2
    assert len(db.products)==3
    diff=db.differences(batch)
    assert db.import_products(batch,'update',diff)==3
    invalid=replace(batch.products[1],values=tuple('broken' if i==5 else v for i,v in enumerate(batch.products[1].values)))
    fresh=ProductDatabase(tmp_path/'fresh')
    with pytest.raises(ValueError):fresh.import_products(ImportResult((batch.products[0],invalid)))
    assert not fresh.products
    with fresh.connection() as con:assert con.execute('SELECT count(*) FROM import_batches').fetchone()[0]==0


def test_foreign_keys_cascade_errors_version(tmp_path,batch):
    path=tmp_path/'db';db=ProductDatabase(path);db.add(batch.products[0])
    db.save_images('000001',[('image1.png',True),('image2.png',False)])
    with pytest.raises(sqlite3.IntegrityError):db.save_images('000001',[('a',True),('b',True)])
    with db.connection() as con:
        assert con.execute('PRAGMA foreign_keys').fetchone()[0]==1
        assert con.execute('PRAGMA user_version').fetchone()[0]==1
        assert con.execute('SELECT count(*) FROM product_images').fetchone()[0]==2
        with pytest.raises(sqlite3.IntegrityError):con.execute("INSERT INTO product_attributes VALUES('missing','color','blue')")
    db.record_errors([(2,'title','empty')])
    db.delete('000001')
    with db.connection() as con:
        assert con.execute('SELECT count(*) FROM product_images').fetchone()[0]==0
        assert con.execute('SELECT count(*) FROM product_attributes').fetchone()[0]==0
        assert con.execute('SELECT excel_row,field FROM import_errors').fetchone()==(2,'title')
        con.execute('PRAGMA user_version=999')
    with pytest.raises(ValueError):ProductDatabase(path)


def test_stale_diff_rejected(tmp_path,batch):
    db=ProductDatabase(tmp_path/'db');db.commit(batch)
    diff=db.differences(batch)
    p=batch.products[0]
    changed=replace(p,values=tuple('other' if i==1 else v for i,v in enumerate(p.values)))
    db.update(changed,db.differences(ImportResult((changed,))))
    with pytest.raises(ValueError):db.import_products(batch,'update',diff)
