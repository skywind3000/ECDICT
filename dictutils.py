#! /usr/bin/env python
# -*- coding: utf-8 -*-
#======================================================================
#
# dictutils.py - 
#
# Created by skywind on 2017/03/31
# Last change: 2017/03/31 22:20:13
#
#======================================================================
import sys
import os
import time
import stardict
import codecs


#----------------------------------------------------------------------
# python3 compatible
#----------------------------------------------------------------------
if sys.version_info[0] >= 3:
	unicode = str
	long = int
	xrange = range


#----------------------------------------------------------------------
# Word Generator
#----------------------------------------------------------------------
class Generator (object):

	def __init__ (self):
		terms = {}
		terms['zk'] = u'中'
		terms['gk'] = u'高'
		terms['ky'] = u'研'
		terms['cet4'] = u'四'
		terms['cet6'] = u'六'
		terms['toefl'] = u'托'
		terms['ielts'] = u'雅'
		terms['gre'] = u'宝'
		self._terms = terms
		names = ('zk', 'gk', 'ky', 'cet4', 'cet6', 'toefl', 'ielts', 'gre')
		self._term_name = names

	def word_tag (self, data):
		tag = data.get('tag', '')
		text = ''
		for term in self._term_name:
			if not tag:
				continue
			if not term in tag:
				continue
			text += self._terms[term]
		frq = data.get('frq')
		if isinstance(frq, str) or isinstance(frq, unicode):
			if frq in ('', '0'):
				frq = None
		if not frq:
			frq = '-'
		bnc = data.get('bnc')
		if isinstance(bnc, str) or isinstance(bnc, unicode):
			if bnc in ('', '0'):
				bnc = None
		if not bnc:
			bnc = '-'
		if bnc != '-' or frq != '-':
			text += ' %s/%s'%(frq, bnc)
		return text.strip()

	def word_level (self, data):
		head = ''
		collins = data.get('collins', '')
		if isinstance(collins, str) or isinstance(collins, unicode):
			if collins in ('', '0'):
				collins = None
		if collins:
			head = str(collins)
		if data.get('oxford'):
			head = 'K' + head
		return head.strip()

	def word_exchange (self, data, style):
		if not data:
			return ''
		exchange = data.get('exchange')
		exchange = stardict.tools.exchange_loads(exchange)
		if not exchange:
			return ''
		part = []
		last = ''
		count = 0
		for k in ('p', 'd', 'i', '3'):
			p = exchange.get(k)
			if p:
				count += 1
				if p != last:
					part.append(u'%s'%p)
					last = p
		if count < 4:
			text = ''
		else:
			text = ', '.join(part)
		origin = ''
		t = exchange.get('0', '')
		if t.lower() == data['word'].lower():
			del exchange['0']
			if '1' in exchange:
				del exchange['1']
		if '0' in exchange:
			t = exchange['0']
			if t != data['word']:
				origin = t
				derive = ''
				if '1' in exchange:
					t = exchange['1']
					p = []
					if 'p' in t and 'd' in t:
						derive = u'过去式和过去分词'
					elif 's' in t and '3' in t:
						derive = u'第三人称单数'
					else:
						for x in ('i', 'p', 'd', '3', 's', 'r', 't'):
							if x in t:
								derive = stardict.tools._exchanges[x]
								break
					if derive:
						origin = data['word'] + u' 是 ' + origin + u' 的' + derive
		better = ''
		if ('r' in exchange) and ('t' in exchange):
			better = exchange['r'] + ', ' + exchange['t']
		lines = []
		# if text and (not exchange.get('1', '') in ('p', 'd', 'i', '3', 'pd', 'dp')):
		if text:
			if style == 0:
				lines.append(u'[时态] ' + text)
			else:
				lines.append(u'时态: ' + text)
		if better and (not exchange.get('1', '') in ('r', 't')):
			if style == 0:
				lines.append(u'[级别] ' + better)
			else:
				lines.append(u'级别: ' + better)
		if origin:
			if style == 0:
				lines.append(u'[原型] ' + origin)
			else:
				lines.append(u'原型: ' + origin)
		return '\n'.join(lines)

	def word_pos (self, data):
		pos = stardict.tools.pos_extract(data)
		if not pos:
			return None
		if len(pos) < 2:
			return None
		text = []
		for mode, num in pos:
			text.append('%s(%s%%)'%(mode[0], num))
		desc = ', '.join(text)
		return desc.replace('\\', '').replace('\n', '')

	def text2html (self, text):
		import cgi
		return cgi.escape(text, True).replace('\n', '</br>')

	# 导出星际译王的词典源文件，用于 DictEditor 转换
	def compile_stardict (self, dictionary, filename, title):
		print('generating ...')
		words = stardict.tools.dump_map(dictionary, False)
		out = {}
		pc = stardict.tools.progress(len(words))
		for word in words:
			pc.next()
			data = dictionary[word]
			phonetic = data['phonetic']
			translation = data['translation']
			if not translation:
				translation = data['definition']
			if not translation:
				print('missing: %s'%word)
				continue
			head = self.word_level(data)
			tag = self.word_tag(data)
			if phonetic:
				if head:
					text = '*[' + phonetic + ']   -' + head + '\n'
				else:
					text = '*[' + phonetic + ']\n'
			elif head:
				text = '-' + head + '\n'
			else:
				text = ''
			text = text + translation
			exchange = self.word_exchange(data, 0)
			if exchange:
				text = text + '\n\n' + exchange + ''
			if tag:
				text = text + '\n' + '(' + tag + ')'
			out[word] = text
		pc.done()
		print('saving ...')
		stardict.tools.export_stardict(out, filename, title)
		return pc.count

	# 导出 Mdx 源文件，然后可以用 MdxBuilder 转换成 .mdx词典
	def compile_mdx (self, dictionary, filename, mode = None, style = False):
		words = stardict.tools.dump_map(dictionary, False)
		fp = codecs.open(filename, 'w', 'utf-8')
		text2html = self.text2html
		pc = stardict.tools.progress(len(words))
		if mode is None:
			mode = ('name', 'phonetic')
		count = 0
		stripword = stardict.stripword
		words = [ k for k in words ]
		words.sort(key = lambda x: stripword(x))
		for word in words:
			pc.next()
			data = dictionary[word]
			phonetic = data['phonetic']
			translation = data['translation']
			if not translation:
				translation = data['definition']
			if not translation:
				continue
			# if pc.count >= 100000:
			# 	break
			head = self.word_level(data)
			tag = self.word_tag(data)
			fp.write(word.replace('\r', '').replace('\n', '') + '\r\n')
			if 'name' in mode:
				if not style:
					fp.write('<b style="font-size:180%%;">%s'%text2html(word))
					fp.write('</b></br></br>\r\n')
				else:
					fp.write('`1`%s`2``2`\r\n'%text2html(word))
			if 'phonetic' in mode:
				if phonetic or head:
					if phonetic:
						if not style:
							fp.write('<font color=dodgerblue>')
							fp.write(text2html(u'[%s]'%phonetic))
							fp.write('</font>')
						else:
							fp.write('`3`' + text2html(u'[%s]'%phonetic))
					if head:
						if phonetic:
							fp.write(' ')
						if not style:
							fp.write('<font color=gray>')
							fp.write(text2html(u'-%s'%head))
							fp.write('</font>')
						else:
							fp.write('`4`' + text2html(u'-%s'%head))
					if not style:
						fp.write('</br></br>\r\n')
					else:
						fp.write('`2``2`\r\n')
			for line in translation.split('\n'):
				line = line.rstrip('\r\n ')
				fp.write(text2html(line) + ' </br>\r\n')
			if (not 'phonetic' in mode) and head:
				if tag:
					tag = tag + ' -' + head
				else:
					tag = '-' + head
			exchange = self.word_exchange(data, 1)
			if exchange:
				if not style:
					fp.write('</br><font color=gray>')
					fp.write(text2html(exchange))
					fp.write('</font>\r\n')
				else:
					fp.write(u'`2``4`' + text2html(exchange) + '`2`\r\n')
			if tag:
				if not style:
					fp.write('</br><font color=gray>')
					fp.write('(%s)'%text2html(tag))
					fp.write('</font>\r\n')
				else:
					fp.write('`2``4`(%s)\r\n'%text2html(tag))
			fp.write('</>')
			if count < len(words) - 1:
				fp.write('\r\n')
			count += 1
		pc.done()
		return pc.count

	def _split_pos (self, text):
		pos = text.find('.')
		if pos < 0:
			return '', text
		if text[:pos].isalpha() and pos < 8:
			return text[:pos + 1], text[pos+1:].lstrip('\t ')
		return '', text

	# 生成支持 css 的 tag
	def _generate_tag (self, fp, data):
		tag = data.get('tag')
		frq = data.get('frq')
		bnc = data.get('bnc')
		if (not tag) and (not frq) and (not bnc):
			return False
		text2html = self.text2html
		out = fp.write
		outline = lambda x: fp.write(x + '\r\n')
		outtext = lambda x: fp.write(text2html(x))
		
		return True

	# 生成支持 css 的 html
	def _generate_html (self, fp, data):
		text2html = self.text2html
		out = fp.write
		outline = lambda x: fp.write(x + '\r\n')
		outtext = lambda x: fp.write(text2html(x))
		word = data['word']
		phonetic = data['phonetic']
		translation = data['translation']
		if not translation:
			translation = data['definition']
		if not translation:
			return False
		outline('<div class="bdy" id="ecdict">')
		outline('<div class="ctn" id="content">')

		# word head
		outline('<div class="hwd">%s</div>'%text2html(word))
		outline('<hr class="hrz">')

		# phonetic and tag
		head = self.word_level(data)
		if phonetic or head:
			outline('<div class="git">')
			if phonetic:
				outline('  <span class="ipa">[%s]</span>'%text2html(phonetic))
			if head:
				outline('  <span class="hnt">-</span>')
			if data.get('oxford'):
				t = u'Oxford 3000 Keywords'
				p = u'<span>\u203B</span>'
				outline('  <span class="oxf" title="%s">%s</span>'%(t, p))
			collins = data.get('collins', '0')
			if isinstance(collins, str) or isinstance(collins, unicode):
				if collins in ('', '0'):
					collins = 0
				else:
					collins = int(collins)
			if collins:
				title = 'Collins Stars'
				out('  <span class="col" title="%s">'%title)
				out(u'\u2605' * int(collins))
				outline('</span>')
			outline('</div>')

		# translation
		outline('<div class="gdc">')
		for line in translation.split('\n'):
			line = line.rstrip('\r\n')
			outline('  <div class="dcb">')
			if line[:4] == u'[网络]':
				text = text2html(line[4:].lstrip('\t '))
				outline(u'    <span class="dnt">[网络]</span>')
				outline(u'    <span class="dne">%s</span>'%text)
			elif line[:1] == '>':
				text = text2html(line)
				outline(u'    <span class="deq">%s</span>'%text)
			else:
				pos, text = self._split_pos(line)
				if pos:
					outline('    <span class="pos">%s</span>'%text2html(pos))
				if text:
					outline('    <span class="dcn">%s</span>'%text2html(text))
			outline('  </div>')
		outline('</div>')

		# exchange
		exchange = self.word_exchange(data, 0)
		if exchange:
			outline('<div class="gfm">')
			for line in exchange.split('\n'):
				line = line.rstrip('\r\n\t ')
				if line.startswith(u'[时态]'):
					text = text2html(line[4:].lstrip(' '))
					outline('  <div class="fmb">')
					outline('    <span class="fnm">%s</span>'%u'时态:')
					outline('    <span class="frm">%s</span>'%text)
					outline('  </div>')
				elif line.startswith(u'[级别]'):
					text = text2html(line[4:].lstrip(' '))
					outline('  <div class="qmb">')
					outline('    <span class="qnm">%s</span>'%u'级别:')
					outline('    <span class="qrm">%s</span>'%text)
					outline('  </div>')
				elif line.startswith(u'[原型]'):
					text = text2html(line[4:].lstrip(' '))
					outline('  <div class="orb">')
					outline('    <span class="onm">%s</span>'%u'原型:')
					outline('    <span class="orm">%s</span>'%text)
					outline('  </div>')
			outline('</div>')

		# tag
		tag = self.word_tag(data)
		if tag:
			title = ''
			frq = data.get('frq')
			bnc = data.get('bnc')
			if frq:
				title = u'COCA: %s'%frq
			if bnc:
				if title:
					title += ', '
				title += 'BNC: %s'%bnc
			outline('<div class="frq" title="%s">'%title)
			outline('  (' + text2html(tag) + ')')
			outline('</div>')
			
		# finalize
		outline('<hr class="hr2"/>')
		outline('</div>')
		outline('</div>')
		return True

	def compile_css (self, dictionary, filename, css = None):
		fp = codecs.open(filename, 'w', 'utf-8')
		text2html = self.text2html
		pc = stardict.tools.progress(len(dictionary))
		if not css:
			main = os.path.split(filename)[-1]
			css = os.path.splitext(main)[0] + '.css'
		for _, word in dictionary:
			pc.next()
			data = dictionary.query(word)
			translation = data['translation']
			if not translation:
				translation = data['definition']
			if not translation:
				continue
			fp.write(word.replace('\r', '').replace('\n', '') + '\r\n')
			fp.write('<link href="%s" rel="stylesheet" type="text/css"/>\r\n'%css)
			self._generate_html(fp, data)
			fp.write('</>')
			if pc.count < pc.total:
				fp.write('\r\n')
		fp.close()
		pc.done()
		return 0

	def list_load (self, filename, encoding = 'utf-8'):
		words = {}
		import codecs
		with codecs.open(filename, encoding = encoding) as fp:
			for line in fp:
				line = line.strip('\r\n\t ')
				if not line:
					continue
				words[line] = 1
		return words

	def list_save (self, filename, words):
		import codecs
		with codecs.open(filename, 'w', encoding = 'utf-8') as fp:
			for w in words:
				fp.write(w + '\n')
		return True

	def mdict2eudic (self, mdx_src, outname, skip = True):
		import codecs
		with codecs.open(mdx_src, encoding = 'utf-8') as srcfp:
			fp = codecs.open(outname, 'w', encoding = 'utf-8')
			word = None
			part = []
			count = 0
			valid = 0
			for line in srcfp:
				line = line.strip('\r\n\t ')
				if not line:
					continue
				if word is None:
					word = line
					part = []
				elif line != '</>':
					part.append(line)
				else:
					invalid = False
					if skip:
						for ch in word:
							if ord(ch) >= 128:
								invalid = True
								break
					if not invalid:
						text = ''.join(part)
						if (not word[:1] == '-') and (not word[-1:] == '-'):
							fp.write(word + '@' + text + '\r\n')
							valid += 1
					word = None
					part = []
					count += 1
					if count % 10000 == 0:
						print('current count=%d'%count)
		print('done valid=%d/%d'%(valid, count))
		return True

	def load_index (self, filename, encoding = 'utf-8', lower = False):
		words = {}
		for line in codecs.open(filename, encoding = encoding):
			line = line.strip('\r\n\t ')
			if not line:
				continue
			if lower:
				words[line.lower()] = line
			else:
				words[line] = line
		return words



#----------------------------------------------------------------------
# 解析 resemble.txt 生成辨析释义
#----------------------------------------------------------------------
class Resemble (object):

	def __init__ (self):
		self._resembles = []
		self._words = {}
		self._filename = None
		self._lineno = 0

	def error (self, text):
		t = '%s:%s: error: %s\n'
		t = t%(self._filename, self._lineno, text)
		sys.stderr.write(t)
		sys.stderr.flush()
	
	def load (self, filename):
		self._resembles = []
		self._words = {}
		file_content = stardict.tools.load_text(filename)
		if file_content is None:
			sys.stderr.write('cannot read: %s\n'%filename)
			return False
		key = None
		content = []
		self._filename = filename
		self._lineno = 0
		for line in file_content.split('\n'):
			line = line.strip('\r\n\t ')
			self._lineno += 1
			if key is None:
				if not line:
					continue
				if line[:1] != '%':
					self.error('must starts with a percent sign')
					return False
				line = line[1:].lstrip('\r\n\t ')
				key = [ n.strip('\r\n\t ') for n in line.split(',') ]
				if not key:
					self.error('empty heading words')
					return False
				for word in key:
					if not word:
						self.error('empty item')
						return False
				content = []
			else:
				if not line:
					wt = {}
					uuid = [ n for n in key ]
					uuid.sort()
					wt['words'] = tuple(key)
					wt['content'] = content
					wt['uuid'] = ', '.join(uuid)
					self._resembles.append(wt)
					key = None
					content = []
				elif line[:1] == '-':
					line = line[1:].lstrip('\r\n\t')
					pos = line.find(':')
					if pos < 0:
						self.error('expect colon')
					word = line[:pos].strip('\r\n\t ')
					text = line[pos+1:].strip('\r\n\t ')
					text = text.replace('\\n', '\n')
					content.append((word, text))
				else:
					content.append(line)
		if key:
			wt = {'words':tuple(key), 'content':content}
			uuid = [ n for n in key ]
			uuid.sort()
			wt['uuid'] = uuid
			self._resembles.append(wt)
		self._init_refs()
		return True

	def _init_refs (self):
		self._words = {}
		words = {}
		existence = {}
		for wt in self._resembles:
			for word in wt['words']:
				if not word in words:
					words[word] = []
				if not word in existence:
					existence[word] = {}
				uuid = wt['uuid']
				if uuid in existence[word]:
					continue
				words[word].append(wt)
				existence[word][uuid] = 1
		for word in words:
			self._words[word] = tuple(words[word])
		return True

	def __len__ (self):
		return len(self._resembles)

	def __getitem__ (self, key):
		if isinstance(key, int) or isinstance(key, long):
			return self._resembles[key]
		return self._words[key]

	def __contains__ (self, key):
		if isinstance(key, int) or isinstance(key, long):
			if key < 0 or key >= len(self._resembles):
				return False
		elif not key in self._words:
			return False
		return True

	def __iter__ (self):
		return self._resembles.__iter__()

	def text2html (self, text):
		import cgi
		return cgi.escape(text, True).replace('\n', '</br>')

	def dump_text (self, wt):
		lines = []
		lines.append('% ' + (', '.join(wt['words'])))
		for content in wt['content']:
			if isinstance(content, list) or isinstance(content, tuple):
				word, text = content
				text = text.replace('\n', '\\n')
				lines.append('- ' + word + ': ' + text)
			else:
				lines.append(content)
		return '\n'.join(lines)

	def dump_html (self, wt, style = 0):
		lines = []
		text2html = self.text2html
		lines.append('<div class="discriminate">')
		text = ', '.join(wt['words'])
		text = '<div class="dis-group"><b>' + text2html(text) + '</b></div>'
		lines.append(text)
		lines.append('<div class="dis-content">')
		for content in wt['content']:
			if isinstance(content, tuple) or isinstance(content, list):
				head = content[0]
				desc = [ n.rstrip('\n') for n in content[1].split('\n') ]
				text = '<font color="dodgerblue">%s</font>: '%text2html(head)
				text = text + text2html(desc[0])
				lines.append(text + '</br>')
				for line in desc[1:]:
					line = line.strip('\r\n\t ')
					if not line:
						continue
					if style == 0:
						lines.append(text2html(line) + '</br>')
					elif style == 1:
						pos = -1
						for i in xrange(len(line)):
							if ord(line[i]) >= 128:
								pos = i
								break
						if pos < 0:
							en, cn = line, ''
						else:
							en, cn = line[:pos], line[pos:]
						en = text2html(en.strip('\r\n\t '))
						cn = text2html(cn.strip('\r\n\t '))
						line = u'<font color=teal>&nbsp;• </font>'
						if en:
							line += '<font color="#008080">%s</font> &nbsp;'%en
						if cn:
							line += ' <font color="gray">%s</font>'%cn
						lines.append('<i>' + line + '</i></br>')
			else:
				lines.append(text2html(content) + '</br>')
		lines.append('</div>')
		lines.append('</div>')
		return '\n'.join(lines)

	def compile_map (self):
		words = {}
		if (not self._resembles) or (not self._words):
			return False
		pc = stardict.tools.progress(len(self._words))
		for word in self._words:
			pc.next()
			if not word:
				continue
			wts = [ self.dump_html(wt, 1) for wt in self._words[word] ]
			words[word] = '</br>\n'.join(wts)
		return words

	def compile_mdx (self, filename):
		words = self.compile_map()
		title = u'有道词语辨析'
		text = time.strftime('%Y-%m-%d %H:%M:%S')
		desc = u'<font color="red">\n'
		desc += u'有道词语辨析</br>\n'
		desc += u'词条数：%d</br>\n'%len(self._words)
		desc += u'词组数：%d</br>\n'%len(self._resembles)
		desc += u'作者：skywind</br>\n'
		desc += u'日期：%s</br>\n'%text
		desc += '</font>'
		stardict.tools.export_mdx(words, filename, title, desc)
		return True



#----------------------------------------------------------------------
# Treasure
#----------------------------------------------------------------------
class Treasure (object):

	def __init__ (self):
		self.mark1 = '<font style="color:#c4151b;margin-right:.2em;font-weight:bold;font-style:italic;">'
		self.generator = Generator()

	def text2html (self, text):
		import cgi
		return cgi.escape(text, True).replace('\n', '</br>')

	def clear_html (self, text):
		return text.replace('<', '').replace('>', '').replace('&', '')

	def detail (self, data, name, default = None):
		detail = data.get('detail')
		if not detail:
			return default
		return detail.get(name, default)

	def define_html (self, definition, plain = False):
		lines = []
		if plain:
			return self.text2html(definition)
		text2html = self.text2html
		for line in definition.split('\n'):
			line = line.rstrip('\r\n\t ')
			if not line:
				pass
			pos = line.find('.')
			head = ''
			if pos > 0 and line[:pos].strip('\t ').isalpha():
				if pos < 8:
					head = line[:pos+1].rstrip(' ')
					line = line[pos+1:].lstrip(' ')
			text = ''
			if head:
				text += self.mark1
				text += text2html(head)
				text += '</font> '
			text += text2html(line)
			lines.append(text)
		return '</br>\n'.join(lines)

	def get_definition (self, data, plain = False):
		definition = data['definition']
		if not definition:
			return None
		return self.define_html(definition, plain)

	def get_translation (self, data, plain = False):
		translation = data['translation']
		if not translation:
			return None
		return self.define_html(translation, plain)

	def get_phonetic (self, data):
		phonetic = data['phonetic']
		if not phonetic:
			return None
		return '[' + self.clear_html(phonetic) + ']'

	def get_level (self, data):
		text = self.generator.word_tag(data)
		head = self.generator.word_level(data)
		if head:
			if text:
				text += ' -' + head
			else:
				text = '-' + head
		if text:
			return self.clear_html(u'(%s)'%text)
		return None

	def get_exchange (self, data):
		text = ''
		exchange = data.get('exchange')
		if not exchange:
			return None
		chg = stardict.tools.exchange_loads(exchange)
		if not chg:
			return None
		part = []
		last = ''
		count = 0
		for k in ('p', 'd', 'i', '3'):
			p = chg.get(k)
			if p:
				count += 1
				if p != last:
					part.append(u'%s'%p)
					last = p
		if count == 4:
			text = ', '.join(part)
			return self.clear_html(u'时态：' + text)
		if ('r' in chg) and ('t' in chg):
			text = ', '.join([chg['r'], chg['t']])
			return self.clear_html(u'级别：' + text)
		return None

	def get_syno (self, data, plain = False):
		detail = data.get('detail')
		if not detail:
			return None
		syno = detail.get('syno')
		if not syno:
			return None
		lines = []
		for group in syno:
			text = group[0]
			word = ', '.join(group[1])
			lines.append('<b>' + self.define_html(text, plain) + '</b>')
			text = '<i>&nbsp;- ' + self.text2html(word) + '</i>'
			lines.append(text)
		return '<br>\n'.join(lines)

	def get_proportion (self, data):
		detail = data.get('detail')
		if not detail:
			return None
		return detail.get('proportion')

	def get_cald (self, data):
		detail = data.get('detail')
		if not detail:
			return None
		html = detail.get('cald')
		if not html:
			return None
		text = html
		mark = '<hr style="height:1px; border:none;  border-top:1px darkblue dashed;"/>'
		p1 = text.find(mark)
		if p1 >= 0:
			text = text[p1 + len(mark):]
		test = '<font color=darkcyan>['
		p1 = text.find(test)
		if p1 >= 0:
			p1 = text.find(']</font>', p1)
			if p1 >= 0:
				text = text[p1+8:]
		newmark = '<hr style="height:1px; border:none;  border-top:1px black dashed; background-color:#ffffff; width:80%"/>'
		text = text.strip('\n\r ')
		text = text.replace(mark, newmark + '\n')
		return text

	def get_collins (self, data):
		return self.detail(data, 'collins', None)

	def get_memo (self, data):
		detail = data.get('detail')
		output = []
		if not detail:
			detail = {}
		youci = detail.get('youci')
		if youci:
			p1 = youci.find('<br>\n')
			if p1 >= 0:
				youci = youci[p1 + 5:]
			if youci:
				head = u'<span class="head">【优词】　</span> '
				head = ''
				output.append(head + youci)
		xdf = detail.get('xdf')
		if xdf:
			head = u'<span class="head">【新东方】　</span>'
			head = ''
			output.append(head + xdf)
		bzsd = detail.get('bzsd')
		if bzsd:
			head = u'<span class="head">【不择手段】　</span>'
			head = ''
			output.append(head + self.text2html(bzsd))
		if not output:
			return None
		return '<br><br>\n'.join(output)

	def get_extra (self, data):
		detail = data.get('detail')
		if not detail:
			return None
		output = []
		resemble = detail.get('resemble')
		if resemble:
			head = u'<span class="head">【有道词语辨析】</div><br>\n'
			head = ''
			output.append(head + resemble)
		syno = detail.get('syno')
		if syno:
			head = u'<span class="head">【有道近义词】</div><br>\n'
			head = ''
			output.append(head + self.get_syno(data))
		if not output:
			return None
		return '<br>\n'.join(output)

	def get_explain (self, data):
		cald = self.get_cald(data)
		if cald:
			return cald
		return self.get_collins(data)

	def generate_front (self, data):
		html = []
		text = "<div style='text-align:center'><h1>%s</h1></div>"
		html.append(text%self.text2html(data['word']))
		html.append("<div style='text-align:center; font-size:85%;'>")
		text = "<span style='font-family: Arial; color:blue;'>%s</span>"
		html.append(text%self.get_phonetic(data))
		text = "<span style='font-family: Arial; color:gray;'>%s</span>"
		html.append(text%self.get_level(data))
		html.append('</div>')
		return '\n'.join(html)

	def generate_back (self, data):
		html = []
		html.append('<div>')
		hr = "height:1px;border:none;border-top:1px dashed #0066CC;"
		hr = hr + "background-color:#ffffff;"
		hr = '<hr style="%s">'%hr
		text = "<div style='color:BlueViolet;text-align:center;font-size:16px;'>%s</div>"
		html.append(text%self.get_translation(data))
		html.append('<br>')
		exchange = self.get_exchange(data)
		if exchange:
			text = "<div style='font-size:12px;color:gray;text-align:center'>%s</div>"
			html.append(text%exchange)
		proportion = self.get_proportion(data)
		if proportion:
			text = u"<div style='font-size:12px;color:gray;text-align:center'>分布：%s</div>"
			html.append(text%proportion)
		html.append(hr)
		memo = self.get_memo(data)
		if memo:
			html.append('<div style="text-align:left;color:#895b8a;font-size:14px;">')
			html.append(memo)
			html.append('</div>')
			html.append(hr)
		explain = self.get_explain(data)
		if explain:
			html.append('<div style="text-align:left;font-size:14px;">')
			html.append(explain)
			html.append('</div>')
		extra = self.get_extra(data)
		if extra:
			html.append(hr)
			html.append('<div style="color:gray;font-size:14px;text-align:left">')
			html.append(extra)
			html.append('</div>')
		html.append('</div>')
		return '\n'.join(html)

	def compile_mdx (self, db, name1, name2):
		mdx1 = {}
		mdx2 = {}
		pc = stardict.tools.progress(len(db))
		for _, word in db:
			pc.next()
			data = db[word]
			mdx1[word] = self.generate_front(data)
			mdx2[word] = self.generate_back(data)
		pc.done()
		if os.path.splitext(name1)[-1].lower() == '.mdx':
			stardict.tools.export_mdx(mdx1, name1, 'anki-front')
		else:
			stardict.tools.export_mdict(mdx1, name1)
		if os.path.splitext(name2)[-1].lower() == '.mdx':
			stardict.tools.export_mdx(mdx2, name2, 'anki-back')
		else:
			stardict.tools.export_mdict(mdx2, name2)
		return 0



#----------------------------------------------------------------------
# generation
#----------------------------------------------------------------------
generator = Generator()
resemble = Resemble()
treasure = Treasure()


#----------------------------------------------------------------------
# testing case
#----------------------------------------------------------------------
if __name__ == '__main__':
	
	def test1():
		db = stardict.open_local('stardict.db')
		data = db['higher']
		# data = {'exchange':'p:P/d:D/i:I/0:haha'}
		print(generator.word_exchange(data, 0))
		print(generator.word_exchange(data, 1))

	def test2():
		resemble.load('resemble.txt')
		# print resemble.dump_text(resemble[0])
		for wt in resemble['stimulate']:
			print resemble.dump_html(wt, 1).encode('gbk', 'ignore')
			print ''
		return 0

	def test3():
		if not resemble.load('resemble.txt'):
			return -1
		fn = u'd:/Program Files/GoldenDict/content/others/有道词语辨析.mdx'
		resemble.compile_mdx(fn)
		return 0

	def test4():
		db = stardict.open_local('treasure.db')
		data = db['breakup']
		# html = treasure.define_html(data['translation'])
		html = treasure.get_collins(data).encode('gbk', 'ignore')
		print html

	def test5():
		name1 = 'anki-front.txt'
		name2 = 'anki-back.txt'
		home = 'd:/Program Files/GoldenDict/content/Others/'
		home = '../../../work/'
		db = stardict.open_local('treasure.db')
		treasure.compile_mdx(db, home + name1, home + name2)

	def test6():
		db = stardict.open_local('ultimate.db')
		data = db['sting']
		data['translation'] += u'\n> hahahah\n[网络] 你好'
		import StringIO
		sio = StringIO.StringIO()
		generator._generate_html(sio, data)
		print sio.getvalue().encode('gbk', 'ignore')

	test6()



