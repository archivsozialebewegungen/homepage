'''
Created on 21.02.2022

@author: michael
'''
from injector import singleton, inject, Injector, Module, provider
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.platypus.doctemplate import SimpleDocTemplate
from reportlab.lib.units import mm
from reportlab.platypus.flowables import Spacer
from reportlab.platypus.paragraph import Paragraph
from datetime import date
import locale
import re
from asb_systematik.SystematikDao import SystematikTree,\
    AlexandriaDbModule, SystematikDao
import roman

styles = getSampleStyleSheet()
re_time = re.compile("(\d+):(\d+):(\d+)\s+\d+:\d+:\d+")

class SystematikExporter(SystematikTree):


    def __init__(self, node_hash):
        
        super().__init__(node_hash)

        self.page_height = A4[1]
        self.page_width = A4[0]
        
        self.sub_list = []
        self.roman_list = []
        
    def export(self, filename="/tmp/Systematik.pdf"):
        
        doc = SimpleDocTemplate(filename, 
                                title = "Systematik des Archivs Soziale Bewegungen",
                                subject = "Systematik",
                                keywords = ("Neue Soziale Bewegungen", "Systematik"),
                                author = "Archiv Soziale Bewegungen e.V., 79098 Freiburg, Adlerstr. 12" )
        
        story = [Spacer(1, 50 * mm)]
        
        story.append(Spacer(1, 10 * mm))
        
        story = self._append_node(self.rootnode, story)

        doc.build(story, onFirstPage=self.first_page, onLaterPages=self.other_pages)
    
    def _append_node(self, node, story):

        depth = node.get_depth()
        
        date_range = ""
        
        if node.startjahr is not None:
            date_range = " (%d)" % node.startjahr
            if node.endjahr is not None:
                if node.endjahr != node.startjahr:
                    date_range = " (%d - %d)" % (node.startjahr, node.endjahr)
        
        
        if node.is_sub():
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph("&nbsp;&nbsp;&nbsp;<b>-</b> <i>%s</i>%s" % (node.beschreibung, date_range), styles["Normal"]))
        elif node.is_roman():
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph("<b>%s</b> <i>%s</i>%s" % (roman.toRoman(node.identifier.roemisch), node.beschreibung, date_range), styles["Normal"]))
        elif depth == 0:
                pass
        elif depth == 1:
            # TODO Pagebreak
            story.append(Paragraph("%s %s%s" % (node.identifier, node.beschreibung, date_range), styles["h1"]))
        elif depth == 2:
            story.append(Paragraph("%s %s%s" % (node.identifier, node.beschreibung, date_range), styles["h2"]))
        elif depth == 3:
            story.append(Paragraph("%s %s%s" % (node.identifier, node.beschreibung, date_range), styles["h3"]))
        elif depth == 4:
            story.append(Paragraph("%s %s%s" % (node.identifier, node.beschreibung, date_range), styles["h4"]))
        elif depth == 5: 
            story.append(Paragraph("%s %s%s" % (node.identifier, node.beschreibung, date_range), styles["h5"]))
        else:
            story.append(Paragraph("<b>%s</b> %s%s" % (node.identifier, node.beschreibung, date_range), styles["Normal"]))
            
        if node.kommentar is not None and node.kommentar.strip() != "":
            story.append(Spacer(1, 2 * mm))
            for part in node.kommentar.split("\n"):
                story.append(Paragraph("%s" % part))
                story.append(Spacer(1, 2 * mm))
            story.append(Spacer(1, 1 * mm))

        for child in node.children:
            story = self._append_node(child, story)
        return story
    
    
    def first_page(self, canvas, doc):
        
        canvas.saveState()
        canvas.setFont('Times-Bold',45)
        canvas.drawCentredString(self.page_width/2.0, self.page_height-108, "ASB-Systematik")
        canvas.setFont('Times-Bold',16)
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
        canvas.drawString(20 * mm, 15 * mm, "ASB-Systematik, Seite %d" % doc.page)
        canvas.restoreState()
        
class SystematikExporterModule(Module):

    @singleton
    @provider
    @inject
    def provide_exporter(self, dao: SystematikDao) -> SystematikExporter:
        return dao.fetch_tree(SystematikExporter)


if __name__ == '__main__':
    locale.setlocale(locale.LC_TIME, "de_DE.UTF-8")
    injector = Injector([AlexandriaDbModule, SystematikExporterModule])
    exporter = injector.get(SystematikExporter)
    exporter.export()