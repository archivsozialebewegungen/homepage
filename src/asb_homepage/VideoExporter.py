'''
Created on 21.02.2022

@author: michael
'''
from pathlib import Path
import os
from xml.dom.minidom import parse
from injector import singleton, inject
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.platypus.doctemplate import SimpleDocTemplate
from reportlab.lib.units import mm
from reportlab.platypus.flowables import Spacer, Image, KeepTogether, PageBreak
from reportlab.platypus.paragraph import Paragraph
from datetime import date
import locale
import re
import ffmpeg
from tinytag import TinyTag

styles = getSampleStyleSheet()
re_time = re.compile("(\d+):(\d+):(\d+)\s+\d+:\d+:\d+")

class Category:
    
    def __init__(self, category_name):
        
        self.category_name = category_name
        self.videos = []
        
class Video:
    
    def __init__(self, filename):

        self.video_codecs = ("h264",)
        self.audio_codecs = ("aac",)
        
        self.filename = filename
        self.title = None
        self.creator = None
        self.duration_in_seconds = None
        self.comment = None
        self.without_sound = True
        self.codecs = []
        self.format = None
        
        self.read_information()
        
    def read_information(self):
        
        tags = TinyTag.get(self.filename)

        self.title = tags.title
        self.creator = tags.artist
        self.comment = tags.comment
        self.year = tags.year
        self.duration_in_seconds = tags.duration
        
        file_info = ffmpeg.probe(self.filename)["streams"]
        stream_counter = 0
        for element in file_info:
            stream_counter += 1
            try:
                codec = element["codec_name"]
                if codec not in self.codecs:
                    self.codecs.append(codec)
                if codec in self.audio_codecs:
                    self.without_sound = False
            except KeyError:
                pass
            try:
                self.format = element["pix_fmt"]
            except KeyError:
                pass
            
    def _get_duration(self):
        
        minutes = int(self.duration_in_seconds / 60)
        hours = int(minutes / 60)
        seconds = int(self.duration_in_seconds - hours * 60 * 60 - minutes * 60)
        return "%0.2d:%0.2d:%0.2d" % (hours, minutes, seconds)
        
        
    duration = property(_get_duration)

@singleton
class VideoInformationCollector:
    
    def __init__(self, start_dir=os.path.join("/", "srv", "AudiovisuelleMedien", "Video")):

        self.file_suffixes = (".mp4", ".mpg", "mpeg", ".avi", ".mov")
        self.start_dir = start_dir
        
    def find_videos(self):
 
        video_categories = {}       
        for (root, _, files) in os.walk(os.path.join("/", "srv", "AudiovisuelleMedien", "Video"), topdown=True):
            video_categories = self.add_files(video_categories, root, files)
        
        return video_categories

    def add_files(self, video_categories, root, files):

        if len(files) == 0:
            return video_categories
        
        dir_name = Path(root).name
        category_name = dir_name.replace("_", " ")
        
        for file in files:
            if file[-4:] in self.file_suffixes:
                if not category_name in video_categories:
                    video_categories[category_name] = []
                video_categories[category_name].append(Video(os.path.join(root, file)))

        return video_categories

@singleton
class VideoExporter():
    
    @inject
    def __init__(self, collector: VideoInformationCollector):
        
        self.page_height = A4[1]
        self.page_width = A4[0]
        self.collector = collector
        
    def export(self, filename=os.path.join("/", "tmp", "videos.pdf")):
        
        doc = SimpleDocTemplate(filename, 
                                title = "Filme im Archiv Soziale Bewegungen",
                                subject = "Filme",
                                keywords = ("Neue Soziale Bewegungen", "Filme"),
                                author = "Archiv Soziale Bewegungen e.V., 79098 Freiburg, Adlerstr. 12" )
        
        story = [Spacer(1, 50 * mm)]
        
        story.append(Spacer(1, 10 * mm))

        categories = self.collector.find_videos()
        
        for category in categories:
            
            story.append(Paragraph(category, styles['h1']))
                         
            for video in sorted(categories[category], key=lambda a: a.title):
                story.append(Paragraph(video.title, styles["h2"]))
                self._add_to_story(story, "Datei: %s" % video.filename)
                self._add_to_story(story, "Jahr: %s" % video.year)
                self._add_to_story(story, "Urheber: %s" % video.creator)
                self._add_to_story(story, "Dauer: %s h" % video.duration)
                if video.without_sound:
                    self._add_to_story(story, "Kein Ton")
                self._add_to_story(story, "Kommentar: %s" % video.comment)
                
            
        doc.build(story, onFirstPage=self.first_page, onLaterPages=self.other_pages)
    
    def _add_to_story(self, story, text, style="Normal"):
        
        if text == None:
            return story
        story.append(Paragraph(text, styles[style]))
        return story
        
    def first_page(self, canvas, doc):
        
        canvas.saveState()
        canvas.setFont('Times-Bold',45)
        canvas.drawCentredString(self.page_width/2.0, self.page_height-108, "Filme")
        canvas.setFont('Times-Bold',32)
        canvas.drawCentredString(self.page_width/2.0, self.page_height-150, "Archiv Soziale Bewegungen e.V.")
        canvas.drawCentredString(self.page_width/2.0, self.page_height-190, "Adlerstr.12, 79098 Freiburg")
        canvas.setFont('Times-Bold',16)
        canvas.drawCentredString(self.page_width/2.0, self.page_height-225, "Stand: %s" % date.today().strftime("%d. %B %Y"))

        canvas.setFont('Times-Roman',9)
        canvas.drawString(20 * mm , 15 * mm, "Filme im ASB, Seite 1")
        canvas.restoreState()
        
    def other_pages(self, canvas, doc):
        
        canvas.saveState()
        canvas.setFont('Times-Roman',9)
        canvas.drawString(20 * mm, 15 * mm, "Filme im ASB, Seite %d" % doc.page)
        canvas.restoreState()  
    
if __name__ == '__main__':
    locale.setlocale(locale.LC_TIME, "de_DE.UTF-8")
    collector = VideoInformationCollector() 
    exporter = VideoExporter(collector)
    exporter.export()