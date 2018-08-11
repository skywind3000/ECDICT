#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim: set ts=4 sw=4 tw=0 noet :
#======================================================================
#
# stardict.py - 
#
# Created by skywind on 2011/05/13
# Last Modified: 2018/08/11 14:11
#
#======================================================================
from __future__ import print_function
import sys
import time
import os
import io
import csv
import sqlite3
import codecs

try:
	import json
except:
	import simplejson as json

MySQLdb = None


#----------------------------------------------------------------------
# python3 compatible
#----------------------------------------------------------------------
if sys.version_info[0] >= 3:
	unicode = str
	long = int
	xrange = range


#----------------------------------------------------------------------
# word strip
#----------------------------------------------------------------------
def stripword(word):
	return (''.join([ n for n in word if n.isalnum() ])).lower()


#----------------------------------------------------------------------
# StarDict 
#----------------------------------------------------------------------
class StarDict (object):

	def __init__ (self, filename, verbose = False):
		self.__dbname = filename
		if filename != ':memory:':
			os.path.abspath(filename)
		self.__conn = None
		self.__verbose = verbose
		self.__open()

	# 初始化并创建必要的表格和索引
	def __open (self):
		sql = '''
		CREATE TABLE IF NOT EXISTS "stardict" (
			"id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL UNIQUE,
			"word" VARCHAR(64) COLLATE NOCASE NOT NULL UNIQUE,
			"sw" VARCHAR(64) COLLATE NOCASE NOT NULL,
			"phonetic" VARCHAR(64),
			"definition" TEXT,
			"translation" TEXT,
			"pos" VARCHAR(16),
			"collins" INTEGER DEFAULT(0),
			"oxford" INTEGER DEFAULT(0),
			"tag" VARCHAR(64),
			"bnc" INTEGER DEFAULT(NULL),
			"frq" INTEGER DEFAULT(NULL),
			"exchange" TEXT,
			"detail" TEXT,
			"audio" TEXT
		);
		CREATE UNIQUE INDEX IF NOT EXISTS "stardict_1" ON stardict (id);
		CREATE UNIQUE INDEX IF NOT EXISTS "stardict_2" ON stardict (word);
		CREATE INDEX IF NOT EXISTS "stardict_3" ON stardict (sw, word collate nocase);
		CREATE INDEX IF NOT EXISTS "sd_1" ON stardict (word collate nocase);
		'''

		self.__conn = sqlite3.connect(self.__dbname, isolation_level = "IMMEDIATE")
		self.__conn.isolation_level = "IMMEDIATE"

		sql = '\n'.join([ n.strip('\t') for n in sql.split('\n') ])
		sql = sql.strip('\n')

		self.__conn.executescript(sql)
		self.__conn.commit()

		fields = ( 'id', 'word', 'sw', 'phonetic', 'definition', 
			'translation', 'pos', 'collins', 'oxford', 'tag', 'bnc', 'frq', 
			'exchange', 'detail', 'audio' )
		self.__fields = tuple([(fields[i], i) for i in range(len(fields))])
		self.__names = { }
		for k, v in self.__fields:
			self.__names[k] = v
		self.__enable = self.__fields[3:]
		return True

	# 数据库记录转化为字典
	def __record2obj (self, record):
		if record is None:
			return None
		word = {}
		for k, v in self.__fields:
			word[k] = record[v]
		if word['detail']:
			text = word['detail']
			try:
				obj = json.loads(text)
			except:
				obj = None
			word['detail'] = obj
		return word

	# 关闭数据库
	def close (self):
		if self.__conn:
			self.__conn.close()
		self.__conn = None
	
	def __del__ (self):
		self.close()

	# 输出日志
	def out (self, text):
		if self.__verbose:
			print(text)
		return True

	# 查询单词
	def query (self, key):
		c = self.__conn.cursor()
		record = None
		if isinstance(key, int) or isinstance(key, long):
			c.execute('select * from stardict where id = ?;', (key,))
		elif isinstance(key, str) or isinstance(key, unicode):
			c.execute('select * from stardict where word = ?', (key,))
		else:
			return None
		record = c.fetchone()
		return self.__record2obj(record)

	# 查询单词匹配
	def match (self, word, limit = 10, strip = False):
		c = self.__conn.cursor()
		if not strip:
			sql = 'select id, word from stardict where word >= ? '
			sql += 'order by word collate nocase limit ?;'
			c.execute(sql, (word, limit))
		else:
			sql = 'select id, word from stardict where sw >= ? '
			sql += 'order by sw, word collate nocase limit ?;'
			c.execute(sql, (stripword(word), limit))
		records = c.fetchall()
		result = []
		for record in records:
			result.append(tuple(record))
		return result

	# 批量查询
	def query_batch (self, keys):
		sql = 'select * from stardict where '
		if keys is None:
			return None
		if not keys:
			return []
		querys = []
		for key in keys:
			if isinstance(key, int) or isinstance(key, long):
				querys.append('id = ?')
			elif key is not None:
				querys.append('word = ?')
		sql = sql + ' or '.join(querys) + ';'
		query_word = {}
		query_id = {}
		c = self.__conn.cursor()
		c.execute(sql, tuple(keys))
		for row in c:
			obj = self.__record2obj(row)
			query_word[obj['word'].lower()] = obj
			query_id[obj['id']] = obj
		results = []
		for key in keys:
			if isinstance(key, int) or isinstance(key, long):
				results.append(query_id.get(key, None))
			elif key is not None:
				results.append(query_word.get(key.lower(), None))
			else:
				results.append(None)
		return tuple(results)

	# 取得单词总数
	def count (self):
		c = self.__conn.cursor()
		c.execute('select count(*) from stardict;')
		record = c.fetchone()
		return record[0]

	# 注册新单词
	def register (self, word, items, commit = True):
		sql = 'INSERT INTO stardict(word, sw) VALUES(?, ?);'
		try:
			self.__conn.execute(sql, (word, stripword(word)))
		except sqlite3.IntegrityError as e:
			self.out(str(e))
			return False
		except sqlite3.Error as e:
			self.out(str(e))
			return False
		self.update(word, items, commit)
		return True

	# 删除单词
	def remove (self, key, commit = True):
		if isinstance(key, int) or isinstance(key, long):
			sql = 'DELETE FROM stardict WHERE id=?;'
		else:
			sql = 'DELETE FROM stardict WHERE word=?;'
		try:
			self.__conn.execute(sql, (key,))
			if commit:
				self.__conn.commit()
		except sqlite3.IntegrityError:
			return False
		return True

	# 清空数据库
	def delete_all (self, reset_id = False):
		sql1 = 'DELETE FROM stardict;'
		sql2 = "UPDATE sqlite_sequence SET seq = 0 WHERE name = 'stardict';"
		try:
			self.__conn.execute(sql1)
			if reset_id:
				self.__conn.execute(sql2)
			self.__conn.commit()
		except sqlite3.IntegrityError as e:
			self.out(str(e))
			return False
		except sqlite3.Error as e:
			self.out(str(e))
			return False
		return True

	# 更新单词数据
	def update (self, key, items, commit = True):
		names = []
		values = []
		for name, id in self.__enable:
			if name in items:
				names.append(name)
				value = items[name]
				if name == 'detail':
					if value is not None:
						value = json.dumps(value, ensure_ascii = False)
				values.append(value)
		if len(names) == 0:
			if commit:
				try:
					self.__conn.commit()
				except sqlite3.IntegrityError:
					return False
			return False
		sql = 'UPDATE stardict SET ' + ', '.join(['%s=?'%n for n in names])
		if isinstance(key, str) or isinstance(key, unicode):
			sql += ' WHERE word=?;'
		else:
			sql += ' WHERE id=?;'
		try:
			self.__conn.execute(sql, tuple(values + [key]))
			if commit:
				self.__conn.commit()
		except sqlite3.IntegrityError:
			return False
		return True

	# 浏览词典
	def __iter__ (self):
		c = self.__conn.cursor()
		sql = 'select "id", "word" from "stardict"'
		sql += ' order by "word" collate nocase;'
		c.execute(sql)
		return c.__iter__()

	# 取得长度
	def __len__ (self):
		return self.count()

	# 检测存在
	def __contains__ (self, key):
		return self.query(key) is not None

	# 查询单词
	def __getitem__ (self, key):
		return self.query(key)

	# 提交变更
	def commit (self):
		try:
			self.__conn.commit()
		except sqlite3.IntegrityError:
			self.__conn.rollback()
			return False
		return True

	# 取得所有单词
	def dumps (self):
		return [ n for _, n in self.__iter__() ]



#----------------------------------------------------------------------
# startup MySQLdb
#----------------------------------------------------------------------
def mysql_startup():
	global MySQLdb
	if MySQLdb is not None:
		return True
	try:
		import MySQLdb as _mysql
		MySQLdb = _mysql
	except ImportError:
		return False
	return True


#----------------------------------------------------------------------
# DictMysql
#----------------------------------------------------------------------
class DictMySQL (object):

	def __init__ (self, desc, init = False, timeout = 10, verbose = False):
		self.__argv = {}
		self.__uri = {}
		if isinstance(desc, dict):
			argv = desc
		else:
			argv = self.__url_parse(desc)
		for k, v in argv.items():
			self.__argv[k] = v
			if k not in ('engine', 'init', 'db', 'verbose'):
				self.__uri[k] = v
		self.__uri['connect_timeout'] = timeout
		self.__conn = None
		self.__verbose = verbose
		self.__init = init
		if 'db' not in argv:
			raise KeyError('not find db name')
		self.__open()

	def __open (self):
		mysql_startup()
		if MySQLdb is None:
			raise ImportError('No module named MySQLdb')
		fields = [ 'id', 'word', 'sw', 'phonetic', 'definition', 
			'translation', 'pos', 'collins', 'oxford', 'tag', 'bnc', 'frq', 
			'exchange', 'detail', 'audio' ]
		self.__fields = tuple([(fields[i], i) for i in range(len(fields))])
		self.__names = { }
		for k, v in self.__fields:
			self.__names[k] = v
		self.__enable = self.__fields[3:]
		self.__db = self.__argv.get('db', 'stardict')
		if not self.__init:
			uri = {}
			for k, v in self.__uri.items():
				uri[k] = v
			uri['db'] = self.__db
			self.__conn = MySQLdb.connect(**uri)
		else:
			self.__conn = MySQLdb.connect(**self.__uri)
			return self.init()
		return True

	# 输出日志
	def out (self, text):
		if self.__verbose:
			print(text)
		return True

	# 初始化数据库与表格
	def init (self):
		database = self.__argv.get('db', 'stardict')
		self.out('create database: %s'%database)
		self.__conn.query("SET sql_notes = 0;")
		self.__conn.query('CREATE DATABASE IF NOT EXISTS %s;'%database)
		self.__conn.query('USE %s;'%database)
		# self.__conn.query('drop table if exists stardict')
		sql = '''
			CREATE TABLE IF NOT EXISTS `%s`.`stardict` (
			`id` INT PRIMARY KEY NOT NULL AUTO_INCREMENT,
			`word` VARCHAR(64) NOT NULL UNIQUE KEY,
			`sw` VARCHAR(64) NOT NULL,
			`phonetic` VARCHAR(64),
			`definition` TEXT,
			`translation` TEXT,
			`pos` VARCHAR(16),
			`collins` SMALLINT DEFAULT 0,
			`oxford` SMALLINT DEFAULT 0,
			`tag` VARCHAR(64),
			`bnc` INT DEFAULT NULL,
			`frq` INT DEFAULT NULL,
			`exchange` TEXT,
			`detail` TEXT,
			`audio` TEXT,
			KEY(`sw`, `word`),
			KEY(`collins`),
			KEY(`oxford`),
			KEY(`tag`)
			)
			'''%(database)
		sql = '\n'.join([ n.strip('\t') for n in sql.split('\n') ])
		sql = sql.strip('\n')
		sql += ' ENGINE=MyISAM DEFAULT CHARSET=utf8;'
		self.__conn.query(sql)
		self.__conn.commit()
		return True

	# 读取 mysql://user:passwd@host:port/database
	def __url_parse (self, url):
		if url[:8] != 'mysql://':
			return None
		url = url[8:]
		obj = {}
		part = url.split('/')
		main = part[0]
		p1 = main.find('@')
		if p1 >= 0:
			text = main[:p1].strip()
			main = main[p1 + 1:]
			p1 = text.find(':')
			if p1 >= 0:
				obj['user'] = text[:p1].strip()
				obj['passwd'] = text[p1 + 1:].strip()
			else:
				obj['user'] = text
		p1 = main.find(':')
		if p1 >= 0:
			port = main[p1 + 1:]
			main = main[:p1]
			obj['port'] = int(port)
		main = main.strip()
		if not main:
			main = 'localhost'
		obj['host'] = main.strip()
		if len(part) >= 2:
			obj['db'] = part[1]
		return obj

	# 数据库记录转化为字典
	def __record2obj (self, record):
		if record is None:
			return None
		word = {}
		for k, v in self.__fields:
			word[k] = record[v]
		if word['detail']:
			text = word['detail']
			try:
				obj = json.loads(text)
			except:
				obj = None
			word['detail'] = obj
		return word

	# 关闭数据库
	def close (self):
		if self.__conn:
			self.__conn.close()
		self.__conn = None

	def __del__ (self):
		self.close()

	# 查询单词
	def query (self, key):
		record = None
		if isinstance(key, int) or isinstance(key, long):
			sql = 'select * from stardict where id = %s;'
		elif isinstance(key, str) or isinstance(key, unicode):
			sql = 'select * from stardict where word = %s;'
		else:
			return None
		with self.__conn as c:
			c.execute(sql, (key,))
			record = c.fetchone()
		return self.__record2obj(record)

	# 查询单词匹配
	def match (self, word, limit = 10, strip = False):
		c = self.__conn.cursor()
		if not strip:
			sql = 'select id, word from stardict where word >= %s '
			sql += 'order by word limit %s;'
			c.execute(sql, (word, limit))
		else:
			sql = 'select id, word from stardict where sw >= %s '
			sql += 'order by sw, word limit %s;'
			c.execute(sql, (stripword(word), limit))
		records = c.fetchall()
		result = []
		for record in records:
			result.append(tuple(record))
		return result

	# 批量查询
	def query_batch (self, keys):
		sql = 'select * from stardict where '
		if keys is None:
			return None
		if not keys:
			return []
		querys = []
		for key in keys:
			if isinstance(key, int) or isinstance(key, long):
				querys.append('id = %s')
			elif key is not None:
				querys.append('word = %s')
		sql = sql + ' or '.join(querys) + ';'
		query_word = {}
		query_id = {}
		with self.__conn as c:
			c.execute(sql, tuple(keys))
			for row in c:
				obj = self.__record2obj(row)
				query_word[obj['word'].lower()] = obj
				query_id[obj['id']] = obj
		results = []
		for key in keys:
			if isinstance(key, int) or isinstance(key, long):
				results.append(query_id.get(key, None))
			elif key is not None:
				results.append(query_word.get(key.lower(), None))
			else:
				results.append(None)
		return tuple(results)

	# 注册新单词
	def register (self, word, items, commit = True):
		sql = 'INSERT INTO stardict(word, sw) VALUES(%s, %s);'
		try:
			with self.__conn as c:
				c.execute(sql, (word, stripword(word)))
		except MySQLdb.Error as e:
			self.out(str(e))
			return False
		self.update(word, items, commit)
		return True

	# 删除单词
	def remove (self, key, commit = True):
		if isinstance(key, int) or isinstance(key, long):
			sql = 'DELETE FROM stardict WHERE id=%s;'
		else:
			sql = 'DELETE FROM stardict WHERE word=%s;'
		try:
			with self.__conn as c:
				c.execute(sql, (key,))
		except MySQLdb.Error as e:
			self.out(str(e))
			return False
		return True

	# 清空数据库
	def delete_all (self, reset_id = False):
		sql1 = 'DELETE FROM stardict;'
		try:
			with self.__conn as c:
				c.execute(sql1)
		except MySQLdb.Error as e:
			self.out(str(e))
			return False
		return True

	# 更新单词数据
	def update (self, key, items, commit = True):
		names = []
		values = []
		for name, id in self.__enable:
			if name in items:
				names.append(name)
				value = items[name]
				if name == 'detail':
					if value is not None:
						value = json.dumps(value, ensure_ascii = False)
				values.append(value)
		if len(names) == 0:
			if commit:
				try:
					self.__conn.commit()
				except MySQLdb.Error as e:
					self.out(str(e))
					return False
			return False
		sql = 'UPDATE stardict SET ' + ', '.join(['%s=%%s'%n for n in names])
		if isinstance(key, str) or isinstance(key, unicode):
			sql += ' WHERE word=%s;'
		else:
			sql += ' WHERE id=%s;'
		try:
			with self.__conn as c:
				c.execute(sql, tuple(values + [key]))
		except MySQLdb.Error as e:
			self.out(str(e))
			return False
		return True

	# 取得数据量
	def count (self):
		sql = 'SELECT count(*) FROM stardict;'
		try:
			with self.__conn as c:
				c.execute(sql)
				row = c.fetchone()
				return row[0]
		except MySQLdb.Error as e:
			self.out(str(e))
			return -1
		return 0

	# 提交数据
	def commit (self):
		try:
			self.__conn.commit()
		except MySQLdb.Error as e:
			self.out(str(e))
			return False
		return True

	# 取得长度
	def __len__ (self):
		return self.count()

	# 检测存在
	def __contains__ (self, key):
		return self.query(key) is not None

	# 查询单词
	def __getitem__ (self, key):
		return self.query(key)

	# 取得所有单词
	def dumps (self):
		return [ n for _, n in self.__iter__() ]



#----------------------------------------------------------------------
# CSV COLUMNS
#----------------------------------------------------------------------
COLUMN_SIZE = 13
COLUMN_ID = COLUMN_SIZE
COLUMN_SD = COLUMN_SIZE + 1
COLUMN_SW = COLUMN_SIZE + 2


#----------------------------------------------------------------------
# DictCsv
#----------------------------------------------------------------------
class DictCsv (object):

	def __init__ (self, filename, codec = 'utf-8'):
		self.__csvname = None
		if filename is not None:
			self.__csvname = os.path.abspath(filename)
		self.__codec = codec
		self.__heads = ( 'word', 'phonetic', 'definition', 
			'translation', 'pos', 'collins', 'oxford', 'tag', 'bnc', 'frq', 
			'exchange', 'detail', 'audio' )
		heads = self.__heads
		self.__fields = tuple([ (heads[i], i) for i in range(len(heads)) ])
		self.__names = {}
		for k, v in self.__fields:
			self.__names[k] = v
		numbers = []
		for name in ('collins', 'oxford', 'bnc', 'frq'):
			numbers.append(self.__names[name])
		self.__numbers = tuple(numbers)
		self.__enable = self.__fields[1:]
		self.__dirty = False
		self.__words = {}
		self.__rows = []
		self.__index = []
		self.__read()

	def reset (self):
		self.__dirty = False
		self.__words = {}
		self.__rows = []
		self.__index = []
		return True

	def encode (self, text):
		if text is None:
			return None
		text = text.replace('\\', '\\\\').replace('\n', '\\n')
		return text.replace('\r', '\\r')

	def decode (self, text):
		output = []
		i = 0
		if text is None:
			return None
		size = len(text)
		while i < size:
			c = text[i]
			if c == '\\':
				c = text[i + 1:i + 2]
				if c == '\\':
					output.append('\\')
				elif c == 'n':
					output.append('\n')
				elif c == 'r':
					output.append('\r')
				else:
					output.append('\\' + c)
				i += 2
			else:
				output.append(c)
				i += 1
		return ''.join(output)

	# 安全转行整数
	def readint (self, text):
		if text is None:
			return None
		if text == '':
			return 0
		try:
			x = long(text)
		except:
			return 0
		if x < 0x7fffffff:
			return int(x)
		return x

	# 读取文件
	def __read (self):
		self.reset()
		filename = self.__csvname
		if filename is None:
			return False
		if not os.path.exists(self.__csvname):
			return False
		codec = self.__codec
		if sys.version_info[0] < 3:
			fp = open(filename, 'rb')
			content = fp.read()
			if not isinstance(content, type(b'')):
				content = content.encode(codec, 'ignore')
			content = content.replace(b'\r\n', b'\n')
			bio = io.BytesIO()
			bio.write(content)
			bio.seek(0)
			reader = csv.reader(bio)
		else:
			reader = csv.reader(open(filename, encoding = codec))
		rows = []
		index = []
		words = {}
		count = 0
		for row in reader:
			count += 1
			if count == 1:
				continue
			if len(row) < 1:
				continue
			if sys.version_info[0] < 3:
				row = [ n.decode(codec, 'ignore') for n in row ]
			if len(row) < COLUMN_SIZE:
				row.extend([None] * (COLUMN_SIZE - len(row)))
			if len(row) > COLUMN_SIZE:
				row = row[:COLUMN_SIZE]
			word = row[0].lower()
			if word in words:
				continue
			row.extend([0, 0, stripword(row[0])])
			words[word] = 1
			rows.append(row)
			index.append(row)
		self.__rows = rows
		self.__index = index
		self.__rows.sort(key = lambda row: row[0].lower())
		self.__index.sort(key = lambda row: (row[COLUMN_SW], row[0].lower()))
		for index in xrange(len(self.__rows)):
			row = self.__rows[index]
			row[COLUMN_ID] = index
			word = row[0].lower()
			self.__words[word] = row
		for index in xrange(len(self.__index)):
			row = self.__index[index]
			row[COLUMN_SD] = index
		return True

	# 保存文件
	def save (self, filename = None, codec = 'utf-8'):
		if filename is None:
			filename = self.__csvname
		if filename is None:
			return False
		if sys.version_info[0] < 3:
			fp = open(filename, 'wb')
			writer = csv.writer(fp)
		else:
			fp = open(filename, 'w', encoding = codec)
			writer = csv.writer(fp)
		writer.writerow(self.__heads)	
		for row in self.__rows:
			newrow = []
			for n in row:
				if isinstance(n, int) or isinstance(n, long):
					n = str(n)
				elif not isinstance(n, bytes):
					if (n is not None) and sys.version_info[0] < 3:
						n = n.encode(codec, 'ignore')
				newrow.append(n)
			writer.writerow(newrow[:COLUMN_SIZE])
		fp.close()
		return True

	# 对象解码
	def __obj_decode (self, row):
		if row is None:
			return None
		obj = {}
		obj['id'] = row[COLUMN_ID]
		obj['sw'] = row[COLUMN_SW]
		skip = self.__numbers
		for key, index in self.__fields:
			value = row[index]
			if index in skip:
				if value is not None:
					value = self.readint(value)
			elif key != 'detail':
				value = self.decode(value)
			obj[key] = value
		detail = obj.get('detail', None)
		if detail is not None:
			if detail != '':
				detail = json.loads(detail)
			else:
				detail = None
		obj['detail'] = detail
		return obj

	# 对象编码
	def __obj_encode (self, obj):
		row = [ None for i in xrange(len(self.__fields) + 3) ]
		for name, idx in self.__fields:
			value = obj.get(name, None)
			if value is None:
				continue
			if idx in self.__numbers:
				value = str(value)
			elif name == 'detail':
				value = json.dumps(value, ensure_ascii = False)
			else:
				value = self.encode(value)
			row[idx] = value
		return row

	# 重新排序
	def __resort (self):
		self.__rows.sort(key = lambda row: row[0].lower())
		self.__index.sort(key = lambda row: (row[COLUMN_SW], row[0].lower()))
		for index in xrange(len(self.__rows)):
			row = self.__rows[index]
			row[COLUMN_ID] = index
		for index in xrange(len(self.__index)):
			row = self.__index[index]
			row[COLUMN_SD] = index
		self.__dirty = False

	# 查询单词
	def query (self, key):
		if key is None:
			return None
		if self.__dirty:
			self.__resort()
		if isinstance(key, int) or isinstance(key, long):
			if key < 0 or key >= len(self.__rows):
				return None
			return self.__obj_decode(self.__rows[key])
		row = self.__words.get(key.lower(), None)
		return self.__obj_decode(row)

	# 查询单词匹配
	def match (self, word, count = 10, strip = False):
		if len(self.__rows) == 0:
			return []
		if self.__dirty:
			self.__resort()
		if not strip:
			index = self.__rows
			pos = 0
		else:
			index = self.__index
			pos = COLUMN_SW
		top = 0
		bottom = len(index) - 1
		middle = top
		key = word.lower()
		if strip:
			key = stripword(word)
		while top < bottom:
			middle = (top + bottom) >> 1
			if top == middle or bottom == middle:
				break
			text = index[middle][pos].lower()
			if key == text:
				break
			elif key < text:
				bottom = middle
			elif key > text:
				top = middle
		while index[middle][pos].lower() < key:
			middle += 1
			if middle >= len(index):
				break
		cc = COLUMN_ID
		likely = [ (tx[cc], tx[0]) for tx in index[middle:middle + count] ]
		return likely

	# 批量查询
	def query_batch (self, keys):
		return [ self.query(key) for key in keys ]

	# 单词总量
	def count (self):
		return len(self.__rows)

	# 取得长度
	def __len__ (self):
		return len(self.__rows)

	# 取得单词
	def __getitem__ (self, key):
		return self.query(key)

	# 是否存在
	def __contains__ (self, key):
		return self.__words.__contains__(key.lower())

	# 迭代器
	def __iter__ (self):
		record = []
		for index in xrange(len(self.__rows)):
			record.append((index, self.__rows[index][0]))
		return record.__iter__()

	# 注册新单词
	def register (self, word, items, commit = True):
		if word.lower() in self.__words:
			return False
		row = self.__obj_encode(items)
		row[0] = word
		row[COLUMN_ID] = len(self.__rows)
		row[COLUMN_SD] = len(self.__rows)
		row[COLUMN_SW] = stripword(word)
		self.__rows.append(row)
		self.__index.append(row)
		self.__words[word.lower()] = row
		self.__dirty = True
		return True

	# 删除单词
	def remove (self, key, commit = True):
		if isinstance(key, int) or isinstance(key, long):
			if key < 0 or key >= len(self.__rows):
				return False
			if self.__dirty:
				self.__resort()
			key = self.__rows[key][0]
		row = self.__words.get(key, None)
		if row is None:
			return False
		if len(self.__rows) == 1:
			self.reset()
			return True
		index = row[COLUMN_ID]
		self.__rows[index] = self.__rows[len(self.__rows) - 1]
		self.__rows.pop()
		index = row[COLUMN_SD]
		self.__index[index] = self.__index[len(self.__rows) - 1]
		self.__index.pop()
		del self.__words[key]
		self.__dirty = True
		return True

	# 清空所有
	def delete_all (self, reset_id = False):
		self.reset()
		return True

	# 更改单词
	def update (self, key, items, commit = True):
		if isinstance(key, int) or isinstance(key, long):
			if key < 0 or key >= len(self.__rows):
				return False
			if self.__dirty:
				self.__resort()
			key = self.__rows[key][0]
		key = key.lower()
		row = self.__words.get(key, None)
		if row is None:
			return False
		newrow = self.__obj_encode(items)
		for name, idx in self.__fields:
			if idx == 0:
				continue
			if name in items:
				row[idx] = newrow[idx]
		return True

	# 提交变更
	def commit (self):
		if self.__csvname:
			self.save(self.__csvname, self.__codec)
		return True

	# 取得所有单词
	def dumps (self):
		return [ n for _, n in self.__iter__() ]


#----------------------------------------------------------------------
# 词形衍生：查找动词的各种时态，名词的复数等，或反向查找
# 格式为每行一条数据：根词汇 -> 衍生1,衍生2,衍生3
# 可以用 Hunspell数据生成，下面有个日本人做的简版（1.8万组数据）：
# http://www.lexically.net/downloads/version4/downloading%20BNC.htm
#----------------------------------------------------------------------
class LemmaDB (object):

	def __init__ (self):
		self._stems = {}
		self._words = {}
		self._frqs = {}

	# 读取数据
	def load (self, filename, encoding = None):
		content = open(filename, 'rb').read()
		if content[:3] == b'\xef\xbb\xbf':
			content = content[3:].decode('utf-8', 'ignore')
		elif encoding is not None:
			text = content.decode(encoding, 'ignore')
		else:
			text = None
			match = ['utf-8', sys.getdefaultencoding(), 'ascii']
			for encoding in match + ['gbk', 'latin1']:
				try:
					text = content.decode(encoding)
					break
				except:
					pass
			if text is None:
				text = content.decode('utf-8', 'ignore')
		number = 0
		for line in text.split('\n'):
			number += 1
			line = line.strip('\r\n ')
			if (not line) or (line[:1] == ';'):
				continue
			pos = line.find('->')
			if not pos:
				continue
			stem = line[:pos].strip()
			p1 = stem.find('/')
			frq = 0
			if p1 >= 0:
				frq = int(stem[p1 + 1:].strip())
				stem = stem[:p1].strip()
			if not stem:
				continue
			if frq > 0:
				self._frqs[stem] = frq
			for word in line[pos + 2:].strip().split(','):
				p1 = word.find('/')
				if p1 >= 0:
					word = word[:p1].strip()
				if not word:
					continue
				self.add(stem, word.strip())
		return True

	# 保存数据文件
	def save (self, filename, encoding = 'utf-8'):
		stems = list(self._stems.keys())
		stems.sort(key = lambda x: x.lower())
		import codecs
		fp = codecs.open(filename, 'w', encoding)
		output = []
		for stem in stems:
			words = self.get(stem)
			if not words:
				continue
			frq = self._frqs.get(stem, 0)
			if frq > 0:
				stem = '%s/%d'%(stem, frq)
			output.append((-frq, u'%s -> %s'%(stem, ','.join(words))))
		output.sort()
		for _, text in output:
			fp.write(text + '\n')
		fp.close()
		return True

	# 添加一个词根的一个衍生词
	def add (self, stem, word):
		if stem not in self._stems:
			self._stems[stem] = {}
		if word not in self._stems[stem]:
			self._stems[stem][word] = len(self._stems[stem]) 
		if word not in self._words:
			self._words[word] = {}
		if stem not in self._words[word]:
			self._words[word][stem] = len(self._words[word])
		return True

	# 删除一个词根的一个衍生词
	def remove (self, stem, word):
		count = 0
		if stem in self._stems:
			if word in self._stems[stem]:
				del self._stems[stem][word]
				count += 1
			if not self._stems[stem]:
				del self._stems[stem]
		if word in self._words:
			if stem in self._words[word]:
				del self._words[word][stem]
				count += 1
			if not self._words[word]:
				del self._words[word]
		return (count > 0) and True or False

	# 清空数据库
	def reset (self):
		self._stems = {}
		self._words = {}
		return True

	# 根据词根找衍生，或者根据衍生反向找词根
	def get (self, word, reverse = False):
		if not reverse:
			if word not in self._stems:
				if word in self._words:
					return [word]
				return None
			words = [ (v, k) for (k, v) in self._stems[word].items() ]
		else:
			if word not in self._words:
				if word in self._stems:
					return [word]
				return None
			words = [ (v, k) for (k, v) in self._words[word].items() ]
		words.sort()
		return [ k for (v, k) in words ]

	# 知道一个单词求它的词根
	def word_stem (self, word):
		return self.get(word, reverse = True)

	# 总共多少条词根数据
	def stem_size (self):
		return len(self._stems)

	# 总共多少条衍生数据
	def word_size (self):
		return len(self._words)

	def dump (self, what = 'ALL'):
		words = {}
		what = what.lower()
		if what in ('all', 'stem'):
			for word in self._stems:
				words[word] = 1
		if what in ('all', 'word'):
			for word in self._words:
				words[word] = 1
		return words

	def __len__ (self):
		return len(self._stems)

	def __getitem__ (self, stem):
		return self.get(stem)

	def __contains__ (self, stem):
		return (stem in self._stems)

	def __iter__ (self):
		return self._stems.__iter__()



#----------------------------------------------------------------------
# DictHelper
#----------------------------------------------------------------------
class DictHelper (object):

	def __init__ (self):
		self._exchanges = {}
		self._exchanges['p'] = u'过去式'
		self._exchanges['d'] = u'过去分词'
		self._exchanges['i'] = u'现在分词'
		self._exchanges['3'] = u'第三人称单数'
		self._exchanges['r'] = u'比较级'
		self._exchanges['t'] = u'最高级'
		self._exchanges['s'] = u'复数'
		self._exchanges['0'] = u'原型'		# best 的原型是 good
		self._exchanges['1'] = u'类别'		# best 的类别是 good 里的 t
		self._pos = {}
		self._pos['a'] = (u'代词', 'pron.')
		self._pos['c'] = (u'连接词', 'conj.')
		self._pos['d'] = (u'限定词', 'determiner')
		self._pos['i'] = (u'介词', 'prep.')
		self._pos['j'] = (u'形容词', 'adj.')
		self._pos['m'] = (u'数词', 'num.')
		self._pos['n'] = (u'名词', 'n.')
		self._pos['p'] = (u'代词', 'pron.')
		self._pos['r'] = (u'副词', 'adv.')
		self._pos['u'] = (u'感叹词', 'int.')
		self._pos['t'] = (u'不定式标记', 'infm.')
		self._pos['v'] = (u'动词', 'v.')
		self._pos['x'] = (u'否定标记', 'not')

	# 返回一个进度指示条，传入总量，每走一格调用一次 next
	def progress (self, total):
		class ProgressIndicator (object):
			def __init__ (self, total):
				self.count = 0
				self.percent = -1
				self.total = total
				self.timestamp = time.time()
				self.counter = {}
			def next (self):
				if self.total:
					self.count += 1
					pc = self.count * 100 / self.total
					if pc != self.percent:
						self.percent = pc
						print('progress: %d%%'%pc)
			def inc (self, name):
				if name not in self.counter:
					self.counter[name] = 1
				else:
					self.counter[name] += 1
			def done (self):
				t = (time.time() - self.timestamp)
				keys = list(self.counter.keys())
				keys.sort()
				for key in keys:
					print('[%s] -> %d'%(key, self.counter[key]))
				print('[Finished in %d seconds (%d)]'%(t, self.count))
		return ProgressIndicator(total)

	# 返回词典里所有词的 map，默认转为小写
	def dump_map (self, dictionary, lower = True):
		words = {}
		for _, word in dictionary:
			if lower:
				word = word.lower()
			words[word] = 1
		return words

	# 字典差异导出
	def discrepancy_export (self, dictionary, words, outname, opts = ''):
		existence = self.dump_map(dictionary)
		if os.path.splitext(outname)[-1].lower() in ('.txt', '.csv'):
			db = DictCsv(outname)
		else:
			db = StarDict(outname)
		db.delete_all()
		count = 0
		for word in words:
			if word.lower() in existence:
				continue
			if '(' in word:
				continue
			if '/' in word:
				continue
			if '"' in word or '#' in word:
				continue
			if '0' in word or '1' in word or '2' in word or '3' in word:
				continue
			if 's' in opts:
				if word.count(' ') >= 2:
					continue
			if 't' in opts:
				if ' ' in word:
					continue
			if 'p' in opts:
				if '-' in word:
					continue
			try:
				word.encode('ascii')
			except:
				continue
			db.register(word, {'tag':'PENDING'}, False)
			count += 1
		db.commit()
		print('exported %d entries'%count)
		return count

	# 字典差异导入
	def discrepancy_import (self, dictionary, filename, opts = ''):
		existence = self.dump_map(dictionary)
		if os.path.splitext(filename)[-1].lower() in ('.csv', '.txt'):
			db = DictCsv(filename)
		else:
			db = StarDict(filename)
		count = 0
		for word in self.dump_map(db, False):
			data = db[word]
			if data is None:
				continue
			if data['tag'] != 'OK':
				continue
			phonetic = data.get('phonetic', '')
			definition = data.get('definition', '')
			translation = data.get('translation', '')
			update = {}
			if phonetic:
				update['phonetic'] = phonetic
			if definition:
				update['definition'] = definition
			if translation:
				update['translation'] = translation
			if not update:
				continue
			if word.lower() in existence:
				if 'n' not in opts:
					dictionary.update(word, update, False)
			else:
				dictionary.register(word, update, False)
			count += 1
		dictionary.commit()
		print('imported %d entries'%count)
		return count

	# 差异比较（utf-8 的.txt 文件，单词和后面音标释义用tab分割） 
	def deficit_tab_txt (self, dictionary, txt, outname, opts = ''):
		deficit = {}
		for line in codecs.open(txt, encoding = 'utf-8'):
			row = [ n.strip() for n in line.split('\t') ]
			if len(row) < 2:
				continue
			word = row[0]
			deficit[word] = 1
		return self.deficit_export(dictionary, deficit, outname, opts)

	# 导出星际译王的词典文件，根据一个单词到释义的字典
	def export_stardict (self, wordmap, outname, title):
		mainname = os.path.splitext(outname)[0]
		keys = [ k for k in wordmap ]
		keys.sort(key = lambda x: (x.lower(), x))
		import struct
		pc = self.progress(len(wordmap))
		position = 0
		with open(mainname + '.idx', 'wb') as f1:
			with open(mainname + '.dict', 'wb') as f2:
				for word in keys:
					pc.next()
					f1.write(word.encode('utf-8', 'ignore') + b'\x00')
					text = wordmap[word].encode('utf-8', 'ignore')
					f1.write(struct.pack('>II', position, len(text)))
					f2.write(text)
					position += len(text)
			with open(mainname + '.ifo', 'wb') as f3:
				f3.write("StarDict's dict ifo file\nversion=2.4.2\n")
				f3.write('wordcount=%d\n'%len(wordmap))
				f3.write('idxfilesize=%d\n'%f1.tell())
				f3.write('bookname=%s\n'%title.encode('utf-8', 'ignore'))
				f3.write('author=\ndescription=\n')
				import datetime
				ts = datetime.datetime.now().strftime('%Y.%m.%d')
				f3.write('date=%s\nsametypesequence=m\n'%ts)
		pc.done()
		return True

	# 导出 mdict 的源文件
	def export_mdict (self, wordmap, outname):
		keys = [ k for k in wordmap ]
		keys.sort(key = lambda x: x.lower())
		size = len(keys)
		index = 0
		pc = self.progress(size)
		with codecs.open(outname, 'w', encoding = 'utf-8') as fp:
			for key in keys:
				pc.next()
				word = key.replace('</>', '').replace('\n', ' ')
				text = wordmap[key].replace('</>', '')
				if not isinstance(word, unicode):
					word = word.decode('gbk')
				if not isinstance(text, unicode):
					text = text.decode('gbk')
				fp.write(word + '\r\n')
				for line in text.split('\n'):
					line = line.rstrip('\r')
					fp.write(line)
					fp.write('\r\n')
				index += 1
				fp.write('</>' + ((index < size) and '\r\n' or ''))
		pc.done()
		return True

	# 导入mdx源文件
	def import_mdict (self, filename, encoding = 'utf-8'):
		import codecs
		words = {}
		with codecs.open(filename, 'r', encoding = encoding) as fp:
			text = []	
			word = None
			for line in fp:
				line = line.rstrip('\r\n')
				if word is None:
					if line == '':
						continue
					else:
						word = line.strip()
				elif line.strip() != '</>':
					text.append(line)
				else:
					words[word] = '\n'.join(text)
					word = None
					text = []
		return words

	# 直接生成 .mdx文件，需要 writemdict 支持：
	# https://github.com/skywind3000/writemdict
	def export_mdx (self, wordmap, outname, title, desc = None):
		try:
			import writemdict
		except ImportError:
			print('ERROR: can\'t import writemdict module, please install it:')
			print('https://github.com/skywind3000/writemdict')
			sys.exit(1)
		if desc is None:
			desc = u'Create by stardict.py'
		writer = writemdict.MDictWriter(wordmap, title = title, 
				description = desc)
		with open(outname, 'wb') as fp:
			writer.write(fp)
		return True

	# 读取 .mdx 文件，需要 readmdict 支持：
	# https://github.com/skywind3000/writemdict (包含readmdict）
	def read_mdx (self, mdxname, mdd = False):
		try:
			import readmdict
		except ImportError:
			print('ERROR: can\'t import readmdict module, please install it:')
			print('https://github.com/skywind3000/writemdict')
			sys.exit(1)
		words = {}
		if not mdd:
			mdx = readmdict.MDX(mdxname)
		else:
			mdx = readmdict.MDD(mdxname)
		for key, value in mdx.items():
			key = key.decode('utf-8', 'ignore')
			if not mdd:
				words[key] = value.decode('utf-8', 'ignore')
			else:
				words[key] = value
		return words

	# 导出词形变换字符串
	def exchange_dumps (self, obj):
		part = []
		if not obj:
			return None
		for k, v in obj.items():
			k = k.replace('/', '').replace(':', '').strip()
			v = v.replace('/', '').replace(':', '').strip()
			part.append(k + ':' + v)
		return '/'.join(part)

	# 读取词形变换字符串
	def exchange_loads (self, exchg):
		if not exchg:
			return None
		obj = {}
		for text in exchg.split('/'):
			pos = text.find(':')
			if pos < 0:
				continue
			k = text[:pos].strip()
			v = text[pos + 1:].strip()
			obj[k] = v
		return obj

	def pos_loads (self, pos):
		return self.exchange_loads(pos)

	def pos_dumps (self, obj):
		return self.exchange_dumps(obj)

	# 返回词性
	def pos_detect (self, word, pos):
		word = word.lower()
		if pos == 'a':
			if word in ('a', 'the',):
				return (u'冠词', 'art.')
			if word in ('no', 'every'):
				return (u'形容词', 'adj.')
			return (u'代词', 'pron.')
		if pos in self._pos:
			return self._pos[pos]
		return (u'未知', 'unknow')

	# 返回词形比例
	def pos_extract (self, data):
		if 'pos' not in data:
			return None
		position = data['pos']
		if not position:
			return None
		part = self.pos_loads(position)
		result = []
		for x in part:
			result.append((x, part[x]))
		result.sort(reverse = True, key = lambda t: int(t[1]))
		final = []
		for pos, num in result:
			mode = self.pos_detect(data['word'], pos)
			final.append((mode, num))
		return final

	# 设置详细内容，None代表删除
	def set_detail (self, dictionary, word, item, value, create = False):
		data = dictionary.query(word)
		if data is None:
			if not create:
				return False
			dictionary.register(word, {}, False)
			data = {}
		detail = data.get('detail')
		if not detail:
			detail = {}
		if value is not None:
			detail[item] = value
		elif item in detail:
			del detail[item]
		if not detail:
			detail = None
		dictionary.update(word, {'detail': detail}, False)
		return True

	# 取得详细内容
	def get_detail (self, dictionary, word, item):
		data = dictionary.query(word)
		if not data:
			return None
		detail = data.get('detail')
		if not detail:
			return None
		return detail.get(item, None)

	# load file and guess encoding
	def load_text (self, filename, encoding = None):
		content = None
		try:
			content = open(filename, 'rb').read()
		except:
			return None
		if content[:3] == b'\xef\xbb\xbf':
			text = content[3:].decode('utf-8')
		elif encoding is not None:
			text = content.decode(encoding, 'ignore')
		else:
			text = None
			guess = [sys.getdefaultencoding(), 'utf-8']
			if sys.stdout and sys.stdout.encoding:
				guess.append(sys.stdout.encoding)
			for name in guess + ['gbk', 'ascii', 'latin1']:
				try:
					text = content.decode(name)
					break
				except:
					pass
			if text is None:
				text = content.decode('utf-8', 'ignore')
		return text

	# csv 读取，自动检测编码
	def csv_load (self, filename, encoding = None):
		text = self.load_text(filename, encoding)
		if not text:
			return None
		import csv
		if sys.version_info[0] < 3:
			import cStringIO
			sio = cStringIO.StringIO(text.encode('utf-8', 'ignore'))
		else:
			import io
			sio = io.StringIO(text)
		reader = csv.reader(sio)
		output = []
		if sys.version_info[0] < 3:
			for row in reader:
				output.append([ n.decode('utf-8', 'ignore') for n in row ])
		else:
			for row in reader:
				output.append(row)
		return output

	# csv保存，可以指定编码
	def csv_save (self, filename, rows, encoding = 'utf-8'):
		import csv
		ispy2 = (sys.version_info[0] < 3)
		if not encoding:
			encoding = 'utf-8'
		if sys.version_info[0] < 3:
			fp = open(filename, 'wb')
			writer = csv.writer(fp)
		else:
			fp = open(filename, 'w', encoding = encoding)
			writer = csv.writer(fp)
		for row in rows:
			newrow = []
			for n in row:
				if isinstance(n, int) or isinstance(n, long):
					n = str(n)
				elif isinstance(n, float):
					n = str(n)
				elif not isinstance(n, bytes):
					if (n is not None) and ispy2:
						n = n.encode(encoding, 'ignore')
				newrow.append(n)
			writer.writerow(newrow)
		fp.close()
		return True

	# 加载 tab 分割的 txt 文件, 返回 key, value
	def tab_txt_load (self, filename, encoding = None):
		words = {}
		content = self.load_text(filename, encoding)
		if content is None:
			return None
		for line in content.split('\n'):
			line = line.strip('\r\n\t ')
			if not line:
				continue
			p1 = line.find('\t')
			if p1 < 0:
				continue
			word = line[:p1].rstrip('\r\n\t ')
			text = line[p1:].lstrip('\r\n\t ')
			text = text.replace('\\n', '\n').replace('\\r', '\r')
			words[word] = text.replace('\\t', '\t').replace('\\\\', '\\')
		return words

	# 保存 tab 分割的 txt文件
	def tab_txt_save (self, filename, words, encoding = 'utf-8'):
		with codecs.open(filename, 'w', encoding = encoding) as fp:
			for word in words:
				text = words[word]
				text = text.replace('\\', '\\\\').replace('\n', '\\n')
				text = text.replace('\r', '\\r').replace('\t', '\\t')
				fp.write('%s\t%s\r\n'%(word, text))
		return True

	# Tab 分割的 txt文件释义导入
	def tab_txt_import (self, dictionary, filename):
		words = self.tab_txt_load(filename)
		if not words:
			return False
		pc = self.progress(len(words))
		for word in words:
			data = dictionary.query(word)
			if not data:
				dictionary.register(word, {'translation':words[word]}, False)
			else:
				dictionary.update(word, {'translation':words[word]}, False)
			pc.inc(0)
			pc.next()
		dictionary.commit()
		pc.done()
		return True

	# mdx-builder 使用writemdict代替MdxBuilder处理较大词典（需64为python）
	def mdx_build (self, srcname, outname, title, desc = None):
		print('loading %s'%srcname)
		t = time.time()
		words = self.import_mdict(srcname)
		t = time.time() - t
		print(u'%d records loaded in %.3f seconds'%(len(words), t))
		print(u'building %s'%outname)
		t = time.time()
		self.export_mdx(words, outname, title, desc)
		t = time.time() - t
		print(u'complete in %.3f seconds'%t)
		return True

	# 验证单词合法性
	def validate_word (self, word, asc128):
		alpha = 0
		for ch in word:
			if ch.isalpha():
				alpha += 1
			if ord(ch) >= 128 and asc128:
				return False
			elif (not ch.isalpha()) and (not ch.isdigit()):
				if ch not in ('-', '\'', '/', '(', ')', ' ', ',', '.'):
					if ch not in ('&', '!', '?', '_'):
						if len(word) == 5 and word[2] == ';':
							continue
						if not ord(ch) in (239, 65292):
							# print 'f1', ord(ch), word.find(ch)
							return False
		if alpha == 0:
			if not word.isdigit():
				return False
		if word[:1] == '"' and word[-1:] == '"':
			return False
		if word[:1] == '(' and word[-1:] == ')':
			if word.count('(') == 1:
				return False
		if word[:3] == '(-)':
			return False
		for ch in ('<', '>', '%', '*', '@', '`'):
			if ch in word:
				return False
		if '%' in word or '\\' in word or '`' in word:
			return False
		if word[:1] in ('$', '@'):
			return False
		if len(word) == 1:
			x = ord(word)
			if (x < ord('a')) and (x > ord('z')):
				if (x < ord('A')) and (x > ord('Z')):
					return False
		if (' ' not in word) and ('-' not in word):
			if ('?' in word) or ('!' in word):
				return False
		if word.count('?') >= 2:
			return False
		if word.count('!') >= 2:
			return False
		if '---' in word:
			return False
		try:
			word.lower()
		except UnicodeWarning:
			return False
		return True


#----------------------------------------------------------------------
# Helper instance
#----------------------------------------------------------------------
tools = DictHelper()

# 根据文件名自动判断数据库类型并打开
def open_dict(filename):
	if isinstance(filename, dict):
		return DictMySQL(filename)
	if filename[:8] == 'mysql://':
		return DictMySQL(filename)
	if os.path.splitext(filename)[-1].lower() in ('.csv', '.txt'):
		return DictCsv(filename)
	return StarDict(filename)


# 字典转化，csv sqlite之间互转
def convert_dict(dstname, srcname):
	dst = open_dict(dstname)
	src = open_dict(srcname)
	dst.delete_all()
	pc = tools.progress(len(src))
	for word in src.dumps():
		pc.next()
		data = src[word]
		x = data['oxford']
		if isinstance(x, int) or isinstance(x, long):
			if x <= 0:
				data['oxford'] = None
		elif isinstance(x, str) or isinstance(x, unicode):
			if x == '' or x == '0':
				data['oxford'] = None
		x = data['collins']
		if isinstance(x, int) or isinstance(x, long):
			if x <= 0:
				data['collins'] = None
		elif isinstance(x, str) or isinstance(x, unicode):
			if x == '' or x == '0':
				data['collins'] = None
		dst.register(word, data, False)
	dst.commit()
	pc.done()
	return True


# 从 ~/.local/share/stardict 下面打开词典
def open_local(filename):
	base = os.path.expanduser('~/.local')
	for dir in [base, base + '/share', base + '/share/stardict']:
		if not os.path.exists(dir):
			os.mkdir(dir)
	fn = os.path.join(base + '/share/stardict', filename)	
	return open_dict(fn)




#----------------------------------------------------------------------
# testing
#----------------------------------------------------------------------
if __name__ == '__main__':
	db = os.path.join(os.path.dirname(__file__), 'test.db')
	my = {'host':'??', 'user':'skywind', 'passwd':'??', 'db':'skywind_t1'}
	def test1():
		t = time.time()
		sd = StarDict(db, False)
		print(time.time() - t)
		# sd.delete_all(True)
		print(sd.register('kiss2', {'definition':'kiss me'}, False))
		print(sd.register('kiss here', {'definition':'kiss me'}, False))
		print(sd.register('Kiss', {'definition':'BIG KISS'}, False))
		print(sd.register('kiss', {'definition':'kiss me'}, False))
		print(sd.register('suck', {'definition':'suck me'}, False))
		print(sd.register('Fuck', {'definition':'fuck me', 'detail':[1,2,3]}, False))
		sd.commit()
		print('')
		print(sd.count())
		print(sd.query('kiSs'))
		print(sd.query(2))
		print(sd.match('kis', 10))
		print('')
		print(sd.query_batch(['fuck', 2]))
		print(sd.match('kisshere', 10, True))
		return 0
	def test2():
		t = time.time()
		dm = DictMySQL(my, init = True)
		print(time.time() - t)
		# dm.delete_all(True)
		print(dm.register('kiss2', {'definition':'kiss me'}, False))
		print(dm.register('kiss here', {'definition':'kiss me'}, False))
		print(dm.register('Kiss', {'definition':'kiss me'}, False))
		print(dm.register('kiss', {'definition':'BIG KISS'}, False))
		print(dm.register('suck', {'definition':'suck me'}, False))
		print(dm.register('Fuck', {'definition':'fuck me'}, False))
		print(dm.query('kiss'))
		print(dm.match('kis'))
		print('')
		print(dm.query('KiSs'))
		print(dm.query_batch(['fuck', 2, 9]))
		print('count: %d'%len(dm))
		print(dm.match('kisshere', 10, True))
		return 0
	def test3():
		csvname = os.path.join(os.path.dirname(__file__), 'test.csv')
		dc = DictCsv(csvname)
		dc.delete_all()
		print(dc.register('kiss2', {'definition':'kiss me'}, False))
		print(dc.register('kiss here', {'definition':'kiss me'}, False))
		print(dc.register('Kiss', {'definition':'kiss me'}, False))
		print(dc.register('kiss', {'definition':'kiss me'}, False))
		print(dc.register('suck', {'definition':'suck me'}, False))
		print(dc.register('word', {'definition':'WORD WORD'}, False))
		print(dc.query('kiss'))
		print('')
		dc.remove('kiss2')
		print(dc.match('kis'))
		print(dc.match('kisshere', 10, True))
		dc.commit()
		return 0
	def test4():
		lemma = LemmaDB()
		t = time.time()
		lemma.load('lemma.en.txt')
		print('load in %s seconds'%str(time.time() - t))
		print(len(lemma))
		for word in ('be', 'give', 'see', 'take'):
			print('%s -> %s'%(word, ','.join(lemma.get(word))))
		for word in ('gave', 'taken', 'looked', 'teeth', 'speak'):
			print('%s <- %s'%(word, ','.join(lemma.word_stem(word))))
		lemma.save('output.txt')
		return 0
	def test5():
		print(tools.validate_word('Hello World', False))
	test3()



