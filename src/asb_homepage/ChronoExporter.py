'''
Created on 21.02.2022

@author: michael
'''
from pathlib import Path
import os
from xml.dom.minidom import parse
from injector import singleton, inject, Injector
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4, A3
from reportlab.platypus.doctemplate import SimpleDocTemplate
from reportlab.lib.units import mm
from reportlab.platypus.flowables import Spacer, Image, KeepTogether, PageBreak
from reportlab.platypus.paragraph import Paragraph
from datetime import date
import locale
import re
from alexandriabase.services import DocumentService, EventService, ServiceModule
from alexplugins.systematic.base import DocumentSystematicRelationsDao,\
    SystematicService
from asb_homepage.InfoReader import InfoReaderModule
from alexandriabase import AlexBaseModule
from alexplugins.cdexporter.base import CDExporterBasePluginModule
from alexplugins.systematic.base import SystematicIdentifier
from alexandriabase.daos import DaoModule, DocumentEventRelationsDao, EventDao,\
    EventCrossreferencesDao, DocumentDao
from asb_systematik.SystematikDao import AlexandriaDbModule
from reportlab.platypus.tables import LongTable, TableStyle
from PIL import Image as PilImage
from _io import BytesIO
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from copy import deepcopy

styles = getSampleStyleSheet()
re_time = re.compile("(\d+):(\d+):(\d+)\s+\d+:\d+:\d+")

@singleton
class ChronoExporter():
    
    @inject
    def __init__(self, systematik_service: SystematicService,
                 reference_dao: DocumentEventRelationsDao,
                 event_xref_dao: EventCrossreferencesDao,
                 event_dao: EventDao,
                 document_dao: DocumentDao):

        self.irrelevant_ids = [1973050004, 1982102802, 1984062601, 1985042701, 1985071701,
                           1986012801, 1987051701, 1990000003, 1990041301, 1990061201,
                           1990070901, 1991062901, 1991121601, 1992032701, 1992091601,
                           1993031501, 1994031401, 1994091004, 1995011401, 1995031401,
                           1995073001, 1996031201, 1998010010, 1998020009, 1998030005,
                           1998040004, 1998050011, 1998050804, 1998051501, 1998052201,
                           1998060001, 1998060101, 1998062001, 1998062701, 1998062801,
                           1998070002, 1998080001, 1998090005, 1998100001, 1998100005,
                           1998110002, 1998120001, 1999010002, 1999020004, 1999030002,
                           1999031201, 1999040007, 1999041604, 1999050012, 1999060008,
                           1999070002, 1999071701, 1999080004, 1999090004, 1999100001,
                           1999110005, 1999120002, 2000010007, 2000020001, 2000030002,
                           2000040002, 2000050004, 2000060006, 2000070003, 2000090002,
                           2000110001, 2000110302, 2000120002, 2001010003, 2001020006,
                           2001030006, 2001040004, 2001050004, 2001060004, 2001070004,
                           2001090007, 2004021105, 2007030801, 2009030801, 2016010801,
                           1982050401, 1998041802, 1998042101, 1998052303, ]
        
        self.ignore_ids = self.irrelevant_ids
        
        pdfmetrics.registerFont(TTFont("Akzidenz", os.path.join(os.path.dirname(__file__), "templates", "fonts", "FontsFree-Net-Akzidenz-grotesk-roman.ttf")))
        pdfmetrics.registerFont(TTFont("AkzidenzBd", os.path.join(os.path.dirname(__file__), "templates", "fonts", "Akzidenz-grotesk-black.ttf")))

        self.mit_ereignis_id = True
        self.normal_style = deepcopy(styles["Normal"])
        self.normal_style.fontSize = 24
        self.normal_style.fontName = "Akzidenz"
        self.normal_style.leading = 26
        self.normal_style.spaceAfter = 60
        
        self.jahr_style = deepcopy(styles["h1"])
        self.jahr_style.fontSize = 32
        self.jahr_style.fontName = "AkzidenzBd"
        self.jahr_breite = 36 * mm
        
        self.topMargin=50*mm
        self.leftMargin=15*mm
        self.rightMargin=10*mm
        
        self.ohne_quellen = False

        self.page_height = A4[1]
        self.page_width = A4[0]
        self.year = 0
        
        self.systematik_service = systematik_service
        self.event_dao = event_dao
        self.reference_dao = reference_dao
        self.event_xref_dao = event_xref_dao
        self.document_dao = document_dao
        
        self.header = self.load_header()
   
    def load_header(self):
        
        pil_image = PilImage.open(os.path.join(os.path.dirname(__file__), "templates", "img", "header_chrono.png"), "r")
        img_stream = BytesIO()
        pil_image.save(img_stream, 'PNG')
        img_stream.seek(0)
        image = Image(img_stream)
        image.hAlign = "LEFT"
        return image
        
    def export_uebersicht(self, filename="/tmp/FeministischeChronologieUebersicht.pdf"):
        
        self.year = 0
        doc = SimpleDocTemplate(filename, 
                                title = "Chronologie feministische Bewegungen",
                                subject = "Ereignisse aus der Alexandria-Datenbank",
                                keywords = ("Neue Soziale Bewegungen", "Buttons"),
                                author = "Archiv Soziale Bewegungen e.V., 79098 Freiburg, Adlerstr. 12" )
        
        story = [Spacer(1, 50 * mm)]
        
        story.append(Spacer(1, 10 * mm))

        event_ids = self.get_events(7)
        event_ids.sort()
        for event_id in event_ids:
            if event_id in self.ignore_ids:
                continue
        
            event = self.event_dao.get_by_id(event_id)
        
            if "Schwul in Freiburg" in event.description:
                continue
        
            self.print_event(story, event)

        doc.build(story, onFirstPage=self.first_page, onLaterPages=self.other_pages)
    
    def export_haeuserkampf(self, filename="/tmp/ChronologieHausbesetzungen.pdf"):
        
        self.year = 0
        doc = SimpleDocTemplate(filename, 
                                title = "Chronologie der Hausbesetzer:innenbewegung",
                                subject = "Ereignisse aus der Alexandria-Datenbank",
                                keywords = ("Neue Soziale Bewegungen", "Hausbesetzungen"),
                                author = "Archiv Soziale Bewegungen e.V., 79098 Freiburg, Adlerstr. 12" )
        
        story = [Spacer(1, 50 * mm)]
        
        story.append(Spacer(1, 10 * mm))

        event_ids = self.get_events(14)
        event_ids.sort()
        for event_id in event_ids:
            event = self.event_dao.get_by_id(event_id)
            self.print_event(story, event)

        doc.build(story, onFirstPage=self.first_page, onLaterPages=self.other_pages)
    
    def export_ausstellung(self, filename="/tmp/FeministischeChronologieA3.pdf"):
        
        self.year = 0
        skip_ids = [1968111701, 1968112001, 1972121502, 1974042503, 1974100402, 1974100601,
                    1974101501, 1974102401, 1974111301, 1975012301, 1975102101, 1975102202,
                    1975102301, 1975102403, 1975102504, 1975121701, 1977022501, 1975021502,
                    1975022203, 1975021502, 1975022203, 1975070702, 1975102002, 1975102503,
                    1978010002, 1978040301, 1978083101, 1979011802, 1979060001, 1975090801,
                    
                    1979040005, 1982050401, 1981030501, 1980050701, 1980071001, 1980072101,
                    1980082501, 1980110801, 1981030501, 1981030801, 1983043001, 1983043002,
                    1985030801, 1985102101, 1987000003, 1987011202, 1987061601, 1987070903,
                    1988062601, 1990050001, 1992090502, 1992112101, 1990011301, 1990030801,
                    1990040001, 1990102501, 1990110303, 1992101201, 1992110201, 1992112501,
                    
                    
                    1993102001, 1994052102, 1996101801, 1997040301, 1997042801, 1963011601,
                    1974040010, 1974042503, 1975053101, 1975070005, 1976060401, 1977110001,
                    1986032101, 1987060501, 1989000001, 1989040502, 1989091902, 1989102901,
                    1989111301, 1990012102, 1990021601, 1990032202, 1990042401, 1990062101,
                    1990062901, 1990070301, 1990092102, 1990100402, 1990110902, 1990111503,
                    
                    1991012701, 1991022202, 1991041603, 1991043002, 1991043002, 1991110101,
                    1991110901, 1991111502, 1991111503, 1992022201, 1992031401, 1992031501,
                    1992032001, 1992032101, 1992032803, 1992032901, 1992052103, 1992052801,
                    1992070502, 1992070901, 1992080102, 1992082302, 1992101001, 1992101201,
                    1992102302, 1992102801, 1992103002, 1992111401, 1992120201, 1993050302,
                    
                    
                    1993052002, 1993082701, 1993100202, 1993101602, 1993103102, 1993110801,
                    1993112201, 1993121102, 1994021702, 1994040503, 1994050701, 1994051002,
                    1994060601, 1994062801, 1994080502, 1994093001, 1994101302, 1994102801,
                    1995042901, 1995101701, 1995103101, 1996052402, 1996092801, 1996100502,
                    1996101903, 1996102402, 1996110801, 1996111502, 1996120102, 1996121402,
                    
                    1997012501, 1997020901, 1997022202, 1997030802, 1997040002, 1997060203,
                    1997061102, 1997102401, 1997102802, 1997103001, 1997111502, 1997112802,
                    1998020001, 1998042202, 1998050008, 1998050501, 1998052102, 1998060007,
                    1998060803, 1998061503, 1998061902, 1998062502, 1998062203, 1998070101,
                    1998080302, 1998082202, 1998101601, 1998112501, 1998120401, 1998121201,
                    
                    
                    1998123101, 1999011301, 1999040004, 1999041403, 1999050001, 1999050011,
                    1999050201, 1999050301, 1999060202, 1999062003, 1999070006, 1999100202,
                    1999101602, 1999102203, 1999102401, 1999110502, 1999112701, 1999070701,
                    1999101602, 1999060902, 1999101603, 1974012803, 1974022802, 1974060801,
                    1975010007, 1975050101, 1975062102, 1975070802, 1975092101, 1976022101,
                    
                    1976091101, 1977010003, 1977022401, 1977041302, 1978060101, 1978061702,
                    1978110201, 1978121502, 1980053101, 1980071501, 1980071601, 1981030802,
                    1981070102, 1981092602, 1981110202, 1982051002, 1982062501, 1982080006,
                    1982062403, 1982062501, 1982080902, 1982120001, 1983070901, 1984031401,
                    1984101902, 1984112002, 1986042502, 1986041902, 1986050008, 1986101502,
                    
                    1986120401, 1987042101, 1987042802, 1987062001, 1987090001, 1988000001,
                    1988030801, 1988050002, 1988112304, 1989040901, 1989051201, 1989102601,
                    1989103102, 1989120601, 1990031001, 1990032801, 1990061301, 1990071201,
                    1990102301, 1990110101, 1991041701, 1991042503, 1991070602, 1991071001,
                    1991081701, 1991120601, 1992030801, 1992031301, 1992040303, 1992051601,
                    
                    1992061802, 1992082501, 1992101202, 1992102202, 1992110301, 1992110401,
                    1992120002, 1992121901, 1993012501, 1993012801, 1993030502, 1993030901,
                    1993050401, 1993060402, 1993062301, 1993090003, 1994031201, 1994111202,
                    1995031301, 1995062401, 1995070303, 1995090001, 1995090101, 1995102101,
                    1995110101, 1995112401, 1995120102, 1995121501, 1996030802, 1996050902,
                    
                    1996051801, 1996053001, 1996060301, 1996061001, 1996061002, 1996062201,
                    1996102801, 1996121901, 1997030701, 1997042501, 1997100901, 1997110801,
                    1997121902, 1998020701, 1998030803, 1998043003, 1998090101, 1998092703,
                    1999032901, 1999042702, 1999060012, 1999060203, 1999061002, 1999080006,
                    1999100008, 1999112502, 1999112702, 2000011002, 2000011802, 2000012101,
                    
                    2000020005, 2000022501, 2000032403, 2000032501, 2000050801, 2000050902,
                    2000050903, 2000060201, 2000062601, 2000070005, 2000070102, 2000071101,
                    2000071201, 2000071202, 2000071301, 2000071503, 2000072401, 2000072702,
                    2000080002, 2000081301, 2000082301, 2000082602, 2000092001, 2000101602,
                    2000111602, 2000120201, 2001020104, 2001020501, 2001032301, 2001042801,
                    
                    2001050501, 2001050502, 2001050901, 2001091901, 2001100502, 2001120101,
                    2002031801, 2002041101, 2002051801, 2002060201, 2002070801, 2002080005,
                    2003030002, 2003030804, 2003030805, 2003061801, 2003081601, 2003112101,
                    2003112601, 2003120101, 2004030803, 2004060101, 2004090102, 2004091501,
                    2004101301, 2005031602, 2005040401, 2005072002, 2006042301, 2006080502,
                    
                    2006090101, 2006120101, 2007030002, 2007050001, 2008040004, 2008052201,
                    2009061101, 2009082501, 2010060301, 2011042901, 2011062301, 2011081302,
                    2011092302, 2011092401, 2011092401, 2011101701, 2013021401, 2013053001,
                    2013061502, 2013102901, 2014052901, 2014111701, 2014112502, 2015031302,
                    2015060301, 2015061201, 2015071001, 2015073001, 2016031002, 2016031301,
                    
                    2016050301, 2016110011, 2017043002, 2017061404, 2017102101, 2017112501,
                    2018030901, 2018080801, 2018111201, 2018112502, 2018112503, 2019021401,
                    2019030702, 2019031502, 2019040901, 2019042601, 2019051701, 2019052201,
                    2019061401, 2019061901, 2019070101, 2019101901, 2019111303, 2019112501,
                    2019112503, 2020013101, 2020010001, 2020041401, 2020042001, 2020042001,
                    
                    2020051503, 2020061301, 2020061302, 2020062701, 2020080201, 2020080401,
                    2020081501, 2020100701, 2020111302, 2020112501, 2021030202, 2021030702,
                    2021031102, 2021032202, 2021032901, 2021042201, 2021042402, 2021042502,
                    2021052801, 2014071201, 2021062602, 2021072101, 2021092801, 2022042201,
                    2022051201, 2022052502, 2022061201, 2022061201, 2022062501,
                    
                    1969042302, 1969050903, 1969060201, 1972041701,
                    ]
        maybe_ids = [1991061901, 1992061902, 1992062701, 2001081801, 2003040005, 2004043002,
                     2004070004, 2004043002, 2004070004, 2015060302, 2017060901, 2020030601,
                     2020110602, 2021070301,
                     
                     1980120001, 1981020002, 1992030701, 1992111301, 2001031002, 2006030801,
                     2011100002, 2014071201, 2021070601, 2020021401, 2021062202, 1983042901,
                     1974040501, 1993052902, 1995090401, 2014000001, 2014030801, 2022062402,
                     1992092303, 1988090002,
                     
                     2001032102, 2016100301, 1974050004, 1979062201
                     ]
        self.ignore_ids = self.irrelevant_ids + skip_ids + maybe_ids
        
        doc = SimpleDocTemplate(filename,
                                pagesize=A3,
                                topMargin=self.topMargin,
                                leftMargin=self.leftMargin,
                                rightMargin=self.rightMargin,
                                title = "Chronologie feministischer Bewegungen",
                                subject = "Ereignisse aus der Alexandria-Datenbank",
                                keywords = ("Neue Soziale Bewegungen", "Buttons"),
                                author = "Archiv Soziale Bewegungen e.V., 79098 Freiburg, Adlerstr. 12" )
        
        story = []
        
        event_ids = self.get_events(7)
        event_ids.sort()
        table_data = []
        for event_id in event_ids:
            if event_id in self.ignore_ids:
                continue
        
            event = self.event_dao.get_by_id(event_id)
        
            if "Schwul in Freiburg" in event.description:
                continue
        
            table_data.append(self.get_columns(event))
            table_data.append(["", ""])
            
        table_style = TableStyle(
            [
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ]
            )    
        story.append(LongTable(data=table_data, colWidths=[self.jahr_breite, None], style=table_style))

        doc.build(story, onFirstPage=self.chrono_page_a3, onLaterPages=self.chrono_page_a3)
    
    def chrono_page_a3(self, canvas, doc):
        
        canvas.saveState()
        canvas.drawImage(os.path.join(os.path.dirname(__file__), "templates", "img", "aufbrechen_header_chrono_sw.tif"), 0, A3[1] - 44.96 * mm, width=A3[0], height=44.96 * mm)
        canvas.restoreState()
    
    def first_page(self, canvas, doc):
        
        canvas.saveState()
        canvas.setFont('Times-Bold',45)
        canvas.drawCentredString(self.page_width/2.0, self.page_height-108, "Chronologie femini-")
        canvas.drawCentredString(self.page_width/2.0, self.page_height-160, "stischer Bewegungen")
        canvas.setFont('Times-Bold',14)
        canvas.drawCentredString(self.page_width/2.0, self.page_height-190, "Archiv Soziale Bewegungen e.V.")
        canvas.drawCentredString(self.page_width/2.0, self.page_height-205, "Adlerstr.12, 79098 Freiburg")
        canvas.drawCentredString(self.page_width/2.0, self.page_height-220, "Stand: %s" % date.today().strftime("%d. %B %Y"))

        canvas.restoreState()
        
    def other_pages(self, canvas, doc):
        
        canvas.saveState()
        canvas.setFont('Times-Roman',9)
        canvas.drawString(20 * mm, 15 * mm, "Chronologie, Seite %d" % doc.page)
        canvas.restoreState()
        
    def get_events(self, systematic: int):
        
        document_ids = self.systematik_service.fetch_document_ids_for_main_systematic(systematic)
        event_dict = {}
        for document_id in document_ids:
            for id in self.reference_dao.fetch_ereignis_ids_for_dokument_id(document_id):
                event_dict[id] = 1
        
        no_of_events = len(event_dict.keys())
        references_found = True
        while references_found:
            ref_events = {}
            for event_id in event_dict.keys():
                for ref in self.event_xref_dao.get_cross_references(event_id):
                    ref_events[ref] = 1
            for event_id in ref_events.keys():
                event_dict[event_id] = 1
            if len(event_dict.keys()) > no_of_events:
                no_of_events = len(event_dict.keys())
            else:
                references_found = False
        
        return list(event_dict.keys())
    
    def print_event(self, story, event):
        
        if self.year < event.daterange.start_date.year:
            self.year = event.daterange.start_date.year
            story.append(Paragraph("%s" % self.year, styles["h1"]))
        if self.mit_ereignis_id:
            story.append(Paragraph("%s ( %d )" % (event.daterange, event.id), styles["h2"]))
        else:
            story.append(Paragraph("%s" % event.daterange, styles["h2"]))
        story.append(Paragraph(event.description, styles["Normal"]))
        
        if self.ohne_quellen:
            story.append(Spacer(1, 10 * mm))
            return
        
        document_ids = self.reference_dao.fetch_document_ids_for_event_id(event.id)
        pars = []
        for document_id in document_ids:
            document = self.document_dao.get_by_id(document_id)
            if "Poppen" in document.description:
                continue 
            if "Dummy" in document.description:
                continue
            pars.append(Paragraph("<b>%s</b>: %s (Alexandria %s)" % (document.document_type, document.description, document.id), styles["Normal"]))
        if len(pars) == 0:
            story.append(Spacer(1, 10 * mm))
            return
        if len(pars) == 1:
            story.append(Paragraph("Quelle", styles["h3"]))
        else:
            story.append(Paragraph("Quellen", styles["h3"]))
        story += pars
        story.append(Spacer(1, 10 * mm))
    
    def get_columns(self, event):
        
        left_column = ""
        if self.year < event.daterange.start_date.year:
            self.year = event.daterange.start_date.year
            left_column = "%s" % self.year
        if self.mit_ereignis_id:
            right_column = "<b>%s:</b> %s ( %s )" % (event.daterange, event.description, event.id)
        else:
            right_column = "<b>%s:</b> %s" % (event.daterange, event.description)
            
        return [Paragraph(left_column, self.jahr_style), Paragraph(right_column, self.normal_style)]
            
if __name__ == '__main__':
    locale.setlocale(locale.LC_TIME, "de_DE.UTF-8")
    injector = Injector([InfoReaderModule, AlexandriaDbModule, AlexBaseModule, CDExporterBasePluginModule, DaoModule, ServiceModule])
    exporter = injector.get(ChronoExporter)
    exporter.ohne_quellen = False
    exporter.mit_ereignis_id = True
    exporter.export_haeuserkampf()
    #exporter.export_uebersicht()
    #exporter.export_ausstellung()