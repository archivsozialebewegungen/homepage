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
from PIL import Image as PilImage
import locale
import re
from _io import BytesIO

styles = getSampleStyleSheet()
re_time = re.compile("(\d+):(\d+):(\d+)\s+\d+:\d+:\d+")

@singleton
class ButtonsExporter():
    
    @inject
    def __init__(self):
        
        self.page_height = A4[1]
        self.page_width = A4[0]
        
    def export(self, filename="/tmp/buttons.pdf"):
        
        doc = SimpleDocTemplate(filename, 
                                title = "Buttons im Archiv Soziale Bewegungen",
                                subject = "Buttons",
                                keywords = ("Neue Soziale Bewegungen", "Buttons"),
                                author = "Archiv Soziale Bewegungen e.V., 79098 Freiburg, Adlerstr. 12" )
        
        story = [Spacer(1, 50 * mm)]
        
        story.append(Spacer(1, 10 * mm))

        reader = DirReader(story, "/srv/Digitalisate/Buttons")
        reader.iterate(DirPrinter, JpgPrinter)
        doc.build(story, onFirstPage=self.first_page, onLaterPages=self.other_pages)
    
    def first_page(self, canvas, doc):
        
        canvas.saveState()
        canvas.setFont('Times-Bold',45)
        canvas.drawCentredString(self.page_width/2.0, self.page_height-108, "Buttons")
        canvas.setFont('Times-Bold',32)
        canvas.drawCentredString(self.page_width/2.0, self.page_height-150, "Archiv Soziale Bewegungen e.V.")
        canvas.drawCentredString(self.page_width/2.0, self.page_height-190, "Adlerstr.12, 79098 Freiburg")
        canvas.setFont('Times-Bold',16)
        canvas.drawCentredString(self.page_width/2.0, self.page_height-225, "Stand: %s" % date.today().strftime("%d. %B %Y"))

        canvas.setFont('Times-Roman',9)
        canvas.drawString(20 * mm , 15 * mm, "Buttons im ASB, Seite 1")
        canvas.restoreState()
        
    def other_pages(self, canvas, doc):
        
        canvas.saveState()
        canvas.setFont('Times-Roman',9)
        canvas.drawString(20 * mm, 15 * mm, "Buttons im ASB, Seite %d" % doc.page)
        canvas.restoreState()  
        
class DirPrinter:
    
    def print(self, story, directory, level):
        
        section = directory.name.replace('_', ' ')
        
        if level == 0:
            return
        if level == 1:
            story.append(PageBreak())
        story.append(Paragraph(section, styles["h%d" % level]))

class JpgPrinter:
    
    def __init__(self, file_path):
        
        self.comments = {}
        self.categories = []
        
        self.file_path = file_path
        self.load_comments()

    def get_text(self, node):
        
        text = ""
        for child_node in node.childNodes:
            if child_node.nodeType == node.TEXT_NODE:
                text += child_node.nodeValue
        return text
        

    def load_comments(self):
        
        info_file = os.path.join(self.file_path.parent, '.comments', self.file_path.name + '.xml')
        if not Path(info_file).exists():
            return
        dom = parse(info_file)
        self.time = None
        for comment_node in dom.documentElement.childNodes:
            if comment_node.nodeType == dom.ELEMENT_NODE:
                if comment_node.tagName == 'categories':
                    self.add_categories(comment_node)
                    continue
                if comment_node.tagName == 'time':
                    timestring = comment_node.getAttribute("value")
                    matcher = re_time.match(timestring)
                    self.time = date(int(matcher.group(1)), int(matcher.group(2)), int(matcher.group(3))).strftime("%d. %B %Y")
                    continue
                self.comments[comment_node.tagName] = self.get_text(comment_node)

    def add_categories(self, categories_node):
        
        for category_node in categories_node.getElementsByTagName('category'):
            self.categories.append(category_node.getAttribute('value'))

    def print(self, story):

        if 'caption' in self.comments and self.comments['caption'].strip() != "":
            caption = Paragraph("<b>%s</b>" % self.comments['caption'], styles['Normal'])
        else:
            caption = Paragraph("<b>Fehlender Titel für %s</b>" % self.file_path.name, styles['Normal'])
        
        pil_image = PilImage.open(self.file_path, "r")
        width, height = pil_image.size
        catalog_size = 100, int(100 * (height/width))
        pil_image.thumbnail(catalog_size, PilImage.ANTIALIAS)
        #image = Image(self.file_path, width=100, height=int(100 * (height/width)))
        img_stream = BytesIO()
        pil_image.save(img_stream, 'PNG')
        img_stream.seek(0)
        image = Image(img_stream)
        image.hAlign = "LEFT"
        
        caption_and_image = KeepTogether([caption, Spacer(1, 5*mm), image]) 
        story.append(caption_and_image)
        
        if 'note' in self.comments:
            story.append(Paragraph(self.comments['note'], styles['Normal']))
        
        if 'place' in self.comments and self.comments['place'].strip() != "":
            story.append(Paragraph("<b>Ort:</b> %s" % self.comments['place'], styles['Normal']))
        if self.time is not None:
            story.append(Paragraph("<b>Datum:</b> %s" % self.time, styles['Normal']))

        for name in self.comments.keys():
            if name == "caption":
                continue
            if name == "note":
                continue
            if name == "place":
                continue
            story.append(Paragraph("<b>%s:</b> %s" % (name, self.comments[name]), styles["Normal"]))
        
        if len(self.categories) > 0:
            output = "<b>Schlagworte:</b> "
        
            trenner = ""
            for category in self.categories:
                output += "%s%s" % (trenner, category)
                trenner = ", "
            story.append(Paragraph(output, styles["Normal"]))
        
        story.append(Spacer(1, 3 * mm))
        

class DirReader:
    
    def __init__(self, story, dir_name, level=0):
        
        self.story = story
        self.level = level
        
        self.directory = Path(dir_name)
        self.jpgs = list(self.directory.glob('*.jpg'))
        self.jpgs.sort(key=lambda x: x.name)
        self.subdirs = [x for x in self.directory.iterdir() if x.is_dir() and x.name != '.comments']
        self.subdirs.sort(key=lambda x: x.name)

    def iterate(self, dir_printer, jpg_printer):
        
        dir_printer().print(self.story, self.directory, self.level)
        
        for jpg in self.jpgs:
            printer = jpg_printer(jpg)
            printer.print(self.story)
            
        for directory in self.subdirs:
            reader = DirReader(self.story, directory, self.level + 1)
            reader.iterate(dir_printer, jpg_printer)
    
if __name__ == '__main__':
    locale.setlocale(locale.LC_TIME, "de_DE.UTF-8")    
    exporter = ButtonsExporter()
    exporter.export()