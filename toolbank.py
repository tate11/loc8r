#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Dilip Kumar <dilipkumar.iitr@gmail.com>

import sys, os, json, urllib2, re, csv
import HTMLParser
#import logging
#import logging.config
from heavins.woo import WooCommerceClient
from mapper import ImageMapper

#logger = logging.getLogger("toolbank-process")
#logging.getLogger("requests").setLevel(logging.CRITICAL)
#logging.getLogger("zeep").setLevel(logging.CRITICAL)

class ToolBankSyncer:

	def __init__(self, woocom, tb):
		self.woocom = woocom
		self.config_tb = tb
		self.ftp = "ftp://%s:%s@%s/" % (tb["user"], tb["pass"], tb["host"])

	def get_export_file(self, file_name):
		url = self.ftp + file_name
		try:
			res = urllib2.urlopen(url, timeout=7200)
			thisFile = res.read().decode("utf-8-sig").encode("utf-8")
		except e:
			print e
		# thisFile = csv.reader(thisFile)
		thisFile = thisFile.split("\r\n")
		return thisFile

	def get_categories_lookup_table(self):
		lookup_table = {}
		h = HTMLParser.HTMLParser()

		categories = self.woocom.get_all_product_categories()
		for cat in categories:
			lookup_table[h.unescape(cat['name'])] = cat['id']
		return lookup_table


	def import_categories(self, products, catKeys):
		main_cat = "TRADE AREA"
		inCategories = self.get_categories_lookup_table()
		try:
			cid = inCategories[main_cat]
		except KeyError as e:
			cid = None
			print e # , " in ", inCategories
			# sys.exit(1)
		if cid == None:
			cat_dump = {"name": main_cat, "slug": main_cat.lower().replace(" ", "-")}
			print "Import Category: ", cat_dump
			inserted = self.woocom.create_product_category(cat_dump)
			#print inserted
			if "id" in inserted:
				cid = inserted["id"] if "id" in inserted else category["data"]["resource_id"]
			else:
				#logger.debug("Could NOT create >>%s<< ", main_cat)
				print "Could not create ", main_cat
				sys.exit(1)
		insertedCat = []
		temp = 0
		# print main_cat, cid, len(products)
		productFiltered = []
		for product in products:
			withCommas = re.findall(r'"(.*?)"', product, re.DOTALL)
			for withComma in withCommas:
				noComma = withComma.replace(",", "__C__")
				product = product.replace(withComma, noComma)
			product = product.strip().split(",")
			plen = len(product)
			for i in range(plen):
				product[i] = product[i].replace("__C__", ",").replace('"', '').replace("\xc2\xae", "")
			productFiltered.append(product)
			cat_id = cid
			print product
			print temp
			temp = temp + 1
			# Adding Category and Sub Category
			for k in catKeys:
				thisCat = product[k].strip()
				cname = thisCat.upper()
				cslug = thisCat.lower().replace(" ", "-")
				if cslug is '' or cslug in insertedCat:
					continue
				try:
					cat_id = inCategories[cname]
					print cname, " in list"
					continue
				except KeyValue:
					# print e
					pass

				cat_dump = {"parent": cat_id, "name": cname, "slug": cslug}
				subCatIn = self.woocom.create_product_category(cat_dump)
				if "id" in subCatIn:
					#logger.debug("\tCreated >>%s<<", cname)
					insertedCat.append(cslug)
					cat_id = subCatIn["id"]
					print "inserted ", cname, " at ", cat_id
				else:
					#logger.debug("\tCould Not create >>%s<<", cname)
					print "Failed: Already in db ", cname
		print "Category imported..."
		return productFiltered

	def import_toolbank_products(self):
		""" Read CSV from FTP and import data to heavins  """
		availibility = []
		fileLines = self.get_export_file('Availability01.csv')[1:]
		# fileLines = []
		for line in fileLines:
			line = line.split(",")
			code = line[0].strip(" ")
			line = line[1:]
			for word in line:
				word = word.strip(" ")
				if word != "" and int(word) != 0:
					availibility.append(code)
				 	#print code
					break

		data = self.get_export_file('ToolbankDataExport.csv')
		keys = data[0].strip().split(",")
		keyCategories = ["ClassAName", "ClassBName", "ClassCName", "ClassDName"]
		inCatKeys = []
		for key in keyCategories:
			inCatKeys.append(keys.index(key.strip()))
		# print inCatKeys
		products = data[1:]
		products = self.import_categories(products, inCatKeys)
		# sys.exit(1)
		finalCategories = self.get_categories_lookup_table()
		len_a = len(availibility)
		len_d = len(products)
		# inUseKeys = ["Product_Name", "CurrentListPrice", "ImageRef", "ProductDescription", "GroupDescription", "StockCode", "Brand_Name", "AnalysisKey1", "AnalysisKey2", "ClassAName", "ClassBName", "ClassCName", "ClassDName"]
		testC = 0
		print len_a, " product available in ", len_d
		for product in products:
			stockCode = product[0]
			if stockCode not in availibility:
				continue
			print stockCode
			name = product[keys.index("Product_Name")]
			slug = name.lower().replace(" ", "-")
			price = product[keys.index("CurrentListPrice")]
			cats = [{"id": finalCategories["TRADE AREA"]}]
			print cats
			for ckey in inCatKeys:
				ctname = product[ckey].strip().upper()
				try:
					cast.append({"id": finalCategories[ctname]})
				except KeyError:
					pass
			description = "%s %s <p>Trade only product SKU: %s and StockCode: %s.</p>" % (product[keys.index("ProductDescription")], product[keys.index("GroupDescription")], "11002", stockCode)

			imageDir = '/var/www/www.heavins.ie/html/toolbank/images/'
			# Do something for images
			# for now I am patching this up by hardcoding
			img = "https://www.heavins.ie/toolbank/images/%.jpg" % (stockCode.upper())
			imagery = [{"src": img, "position": 0}]
			prodData = {
				"name": name,
				"slug": slug,
				"sku": "11002",
				"regular_price": price,
				"manage_stock": True,
				"stock_quantity": 10,
				"shipping_class": "",
				"categories": cats,
				"description": description,
				"images": imagery
			}
			if testC < 10:
				print prodData
				testC = testC+1
				continue
			else:
				sys.exit(1)

			try:
				insertedProduct = self.woocom.create_product(prodData)
			except Exception:
				pass #logger.exception("Data %s", data)



def sync_toolbank(config):
	syncer = ToolBankSyncer(
		WooCommerceClient(
			url=config["woocommerce"]["url"],
			consumer_key=config["woocommerce"]["consumer_key"],
			consumer_secret=config["woocommerce"]["consumer_secret"]
		),
		config["toolbank"]
	)

	syncer.import_toolbank_products()


def main():
	try:
		config_path, _ = os.path.split(os.path.abspath(__file__))
		with open("{0}/config.json".format(config_path)) as config:
			config = json.load(config)
			#logging.config.dictConfig(config["logging"])
	except (IOError, Exception) as e:
		print "Error loading config: {0}".format(e)
		sys.exit(1)


	try:
		#logger.info("*** Starting Toolbank Sync ***")
		print "Starting Export"
		sync_toolbank(config)
		#logger.info("*** ToolBank Sync Completed ***")
	except Exception as e:
		pass #logger.exception("Error syncing Toolbank: %s", e)


if __name__ == '__main__':
	try:
		print "Starting Main..."
		main()
	except KeyboardInterrupt:
		print "*** Keyboard Interrupt caught! ***"
		try:
			sys.exit(0)
		except SystemExit:
			os._exit(0)

