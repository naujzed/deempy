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
	lg = open("downloaded.txt", 'w', encoding='utf-8')
	flg = open("failed.txt", 'w', encoding='utf-8')

	@classmethod
	def send(cls, key, value=None):
		logString = formatListener(key, value)
		if logString:
			print(logString)
		if key == "updateQueue":
			if value.get('downloaded'):
				cls.lg.write(cls.geturl(value["uuid"])+'\n')
			if value.get('failed'):
				cls.flg.write(cls.geturl(value["uuid"])+'\t' +
							  value['error']+'\t'+value['errid']+'\n')
	def geturl(uuid):
		tmp = uuid.split("_")
		return f"https://www.deezer.com/{tmp[0]}/{tmp[1]}\t{tmp[2]}"


class DLR():
	def __init__(self, portable=None, path=None):
		localpath = Path('.')

		self.configFolder = localpath / \
			'config' if portable else localpaths.getConfigFolder()
		self.settings = loadSettings(self.configFolder)
		self.dz = Deezer()
		self.listener = LogListener()
		self.plugins = {}
		if Spotify:
			self.plugins = {
				"spotify": Spotify(configFolder=self.configFolder)
			}
			self.plugins["spotify"].setup()
		if path is not None:
			if path == '':
				path = '.'
			path = Path(path)
			self.settings['downloadLocation'] = str(path)
		self.downloadObjects = []
		self.findarl()

	def requestValidArl(self):
		while True:
			arl = input("Paste here your arl:")
			if self.dz.login_via_arl(arl.strip()):
				break
		return arl

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

	def downloadLinks(self, url, bitrate=None):
		if not bitrate:
			bitrate = self.settings.get("maxBitrate", TrackFormats.MP3_320)
		links = []
		for link in url:
			if ';' in link:
				for l in link.split(";"):
					links.append(l)
			else:
				links.append(link)

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

	def getsongs(self):
		for obj in self.downloadObjects:
			if obj.__type__ == "Convertable":
				obj = self.plugins[obj.plugin].convert(
					self.dz, obj, self.settings, self.listener)
			rs = Downloader(self.dz, obj, self.settings, self.listener).start()
		self.downloadObjects = []

	def download(self, url, bitrate, path, start=None):
		# Check for local configFolder

		url = list(url)
		if bitrate:
			bitrate = getBitrateNumberFromText(bitrate)
		if path is not None:
			if path == '':
				path = '.'
			path = Path(path)
			self.settings['downloadLocation'] = str(path)
		# If first url is filepath readfile and use them as URLs
		try:
			isfile = Path(url[0]).is_file()
		except Exception:
			isfile = False
		if isfile:
			filename = url[0]
			with open(filename) as f:
				url = f.readlines()

		self.downloadLinks(url, bitrate)
		if start:
			print("DLIN")
			self.getsongs()
			click.echo("All done!")

	def change(self,key,value):
		self.settings[key] = value
	def resetSetting(self):
		self.settings = loadSettings(self.configFolder)
	def printSettings(self):
		print("printing settings")
		for k, v in self.settings.items():
			print(f'{k}\n{v}\n\n')
if __name__ == '__main__':
	dl320 = ("downloads320.txt",)
	dlflac = ("downloadsflac.txt",)
	tp = DLR(None, ".")
	tp.printSettings()
	# tp.download(dl320, "320", ".",)
	# tp.download(dlflac, "flac", ".", True)
