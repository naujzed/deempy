#!/usr/bin/env python3
from logging import error
import click
from pathlib import Path

from deezer import Deezer
from deezer import TrackFormats

from deemix import generateDownloadObject
from deemix.settings import load as loadSettings
from deemix.utils import getBitrateNumberFromText, formatListener
import deemix.utils.localpaths as localpaths
from deemix.downloader import Downloader
from deemix.itemgen import GenerationError
try:
	from deemix.plugins.spotify import Spotify
except ImportError:
	Spotify = None


class LogListener:
	
	# opens files to write successful and failed downloads
	def __init__(self,failedFile,successFile):
		self.lg = open(successFile, 'a', encoding='utf-8')
		self.flg = open(failedFile, 'a', encoding='utf-8')
		self.failed = 0

	# deemix call this function for logging to cli 
	def send(self, key, value=None):
		logString = formatListener(key, value)
		if logString:
			print(logString)
		self.writetxt(key,value)
	
	# write whether a track downloaded or failed
	def writetxt(self,key, value=None):
		if key == "updateQueue":
			if value.get('downloaded'):
				self.lg.write(self.geturl(value["uuid"])+'\n')
			if value.get('failed'):
				self.failed +=1
				self.flg.write(self.geturl(value["uuid"])+'\t' + value['error']+'\t'+value['errid']+'\n')
				
	# turns a uuid (<type>_<id>_<bitrate>) to deezer url
	def geturl(self,uuid):
		tmp = uuid.split("_")
		return f"https://www.deezer.com/{tmp[0]}/{tmp[1]}\t{tmp[2]}"


class DLR():
	# protable:Bool - is the config folder in the current directory
	def __init__(self, portable=None,failedFile='failedDL.txt',successFile='Downloaded.txt'):
		self.dz = Deezer()
		self.listener = LogListener(failedFile,successFile)
		self.plugins = {}
		self.downloadObjects = []

		localpath = Path('.')
		self.configFolder = localpath / \
			'config' if portable else localpaths.getConfigFolder()
		self.settings = loadSettings(self.configFolder)

		if Spotify:
			self.plugins = {
				"spotify": Spotify(configFolder=self.configFolder)
			}
			self.plugins["spotify"].setup()

		self.findarl()

	# request an arl token until successful login
	def requestValidArl(self):
		while True:
			arl = input("Paste here your arl:")
			if self.dz.login_via_arl(arl.strip()):
				break
		return arl

	# find arl in config folder or ask for it
	def findarl(self):
		if (self.configFolder / '.arl').is_file():
			with open(self.configFolder / '.arl', 'r') as f:
				arl = f.readline().rstrip("\n").strip()
			if not self.dz.login_via_arl(arl):
				arl = self.requestValidArl()
		else:
			arl = self.requestValidArl()
		with open(self.configFolder / '.arl', 'w') as f:
			f.write(arl)

	# turns deezer urls to DL objects stores them in class.downloadObjects
		# links: list - contains a list of deezer links
		# bitrate: TrackFormat - a trackformat from deezer.TrackFormats
	def addToQueue(self, links, bitrate=None):
		if not bitrate:
			bitrate = self.settings.get("maxBitrate", TrackFormats.MP3_320)

		for link in links:
			try:
				downloadObject = generateDownloadObject(
					self.dz, link, bitrate, self.plugins, self.listener)
			except GenerationError as e:
				print(f"{e.link}: {e.message}")
				continue
			if isinstance(downloadObject, list):
				self.downloadObjects += downloadObject
			else:
				self.downloadObjects.append(downloadObject)

	# starts the download of all downloadObjects in queue then clears it once finished
	def getsongs(self):
		sz = len(self.downloadObjects)
		print(f"DOWNLOADING {sz}")

		for obj in self.downloadObjects:
			if obj.__type__ == "Convertable":
				obj = self.plugins[obj.plugin].convert(
					self.dz, obj, self.settings, self.listener)
			Downloader(self.dz, obj, self.settings, self.listener).start()
		print(f"ALL DONE!: \n\t{self.listener.failed}/{sz} FAILED")
		self.downloadObjects = []

	# reads in links from file or changes bitrate text to TrackFormat
		# url: list - can be a list of urls
		# bitrate: string - choice between 
			# lossleess:['flac', 'lossless', '9'] 
			# mp3:['mp3', '320', '3'] ['128', '1'] 
			# 360:['360', '360_hq', '15'] ['360_mq', '14'] ['360_lq', '13']
		# filepath: string - the filepath to a txt file of urls
	def loadLinks(self, url=None, filepath=None,bitrate=None):

		links = []
		try:
			isfile = Path(filepath).is_file()
		except Exception:
			isfile = False
		if isfile:
			with open(filepath) as f:
				links = f.readlines()
		else:
			if not isinstance(url,list):
				for link in url:
					if ';' in link:
						for l in link.split(";"):
							links.append(l)
					else:
						links.append(link)
			else:
				links = url

		if bitrate:
			bitrate = getBitrateNumberFromText(bitrate)

		self.addToQueue(links, bitrate)

	# change a settings value
	def change(self,key,value):
		self.settings[key] = value
	# reset settings to "default"
	def resetSetting(self):
		self.settings = loadSettings(self.configFolder)
	# print current settings
	def printSettings(self):
		print("printing settings")
		for k, v in self.settings.items():
			print(f'{k}\n{v}\n\n')


if __name__ == '__main__':
	tp = DLR(portable=None,failedFile='failed.txt',successFile='succ.txt')
	
	tp.loadLinks(url=['https://www.deezer.com/en/track/1','https://www.deezer.com/en/track/2'], bitrate="320")
	tp.loadLinks(filepath='downloadsflac.txt', bitrate="flac")

	tp.change('downloadLocation','.')

	tp.getsongs()

