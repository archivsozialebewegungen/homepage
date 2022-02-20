'''
Created on 02.02.2022

@author: michael
'''
from os import path, makedirs
from asb_zeitschriften.broschdaos import ZeitschriftenDao, Zeitschrift,\
    BroschDao, Brosch, PageObject, BroschFilter, ZeitschriftenFilter,\
    JahrgaengeDao
from injector import Injector, inject, singleton
from asb_systematik.SystematikDao import AlexandriaDbModule, SystematikDao,\
    DataError
import zipfile
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus.doctemplate import SimpleDocTemplate
from reportlab.platypus.flowables import Spacer
from reportlab.lib.units import mm
from reportlab.platypus.paragraph import Paragraph
from reportlab.rl_settings import defaultPageSize
from reportlab.lib.pagesizes import A4
from datetime import date
import locale
from alexplugins.cdexporter.base import CDExporterBasePluginModule, ExportInfo,\
    CDDataAssembler, GenerationEngine
import datetime
from alexandriabase import AlexBaseModule
from alexandriabase.daos import DaoModule
from alexandriabase.domain import AlexDate
from alexandriabase.services import ServiceModule

@singleton
class BroschuerenExporter():
    
    @inject
    def __init__(self, brosch_dao: BroschDao):
        
        self.brosch_dao = brosch_dao
        self.styles = getSampleStyleSheet()
        self.page_height = A4[1]
        self.page_width = A4[0]
        
    def export(self, filename="/tmp/broschueren.pdf"):
        
        doc = SimpleDocTemplate(filename, 
                                title = "Broschüren im Archiv Soziale Bewegungen",
                                subject = "Broschüren",
                                keywords = ("Neue Soziale Bewegungen",),
                                author = "Archiv Soziale Bewegungen e.V., 79098 Freiburg, Adlerstr. 12" )
        
        story = [Spacer(1,50 * mm)]
        style = self.styles["Normal"]

        page_object = PageObject(self.brosch_dao, Brosch, BroschFilter(), page_size=100)
        self.brosch_dao.init_page_object(page_object)
        try:
            while True:
                for brosch in page_object.objects:
                    story.append(Paragraph(brosch.titel, self.styles['h2']))
                    if brosch.untertitel is not None:
                        story.append(Paragraph(brosch.untertitel, self.styles['h3']))
                        story.append(Spacer(1, 3 * mm))
                    story.append(Paragraph(brosch.basic_info, style))
                    story.append(Paragraph("<b>Signatur:</b> %s" % brosch.signatur, style))
                    story.append(Spacer(1, 5 * mm))
                page_object.fetch_next()
        except DataError as e:
            pass
            
        doc.build(story, onFirstPage=self.first_page, onLaterPages=self.other_pages)
    
    def _add_field(self, story, value, definition):
        
        if value is None or value.strip() == '':
            return
        story.append(Paragraph("<b>%s:</b> %s" % (definition, value), self.styles["Normal"]))
        story.append(Spacer(1, 3 * mm))

    def first_page(self, canvas, doc):
        
        canvas.saveState()
        canvas.setFont('Times-Bold',45)
        canvas.drawCentredString(self.page_width/2.0, self.page_height-108, "Broschüren")
        canvas.setFont('Times-Bold',32)
        canvas.drawCentredString(self.page_width/2.0, self.page_height-150, "Archiv Soziale Bewegungen e.V.")
        canvas.drawCentredString(self.page_width/2.0, self.page_height-180, "Adlerstr.12, 79098 Freiburg")

        canvas.setFont('Times-Roman',9)
        canvas.drawString(20 * mm , 15 * mm, "Broschüren im ASB, Seite 1")
        canvas.restoreState()
        
    def other_pages(self, canvas, doc):
        
        canvas.saveState()
        canvas.setFont('Times-Roman',9)
        canvas.drawString(20 * mm, 15 * mm, "Broschüren im ASB, Seite %d" % doc.page)
        canvas.restoreState()  
        
    def _print_field(self, value, definition):
        
        if value is None or value.strip() == '':
            return
        print("%s: %s" % (definition, value))        


@singleton
class ZeitschriftenExporter():
    
    @inject
    def __init__(self, zeitschriften_dao: ZeitschriftenDao, jahrgaenge_dao: JahrgaengeDao):
        
        self.zeitschriften_dao = zeitschriften_dao
        self.jahrgaenge_dao = jahrgaenge_dao
        self.styles = getSampleStyleSheet()
        self.page_height = A4[1]
        self.page_width = A4[0]
        
    def export(self, filename="/tmp/zeitschriften.pdf"):
        
        doc = SimpleDocTemplate(filename, 
                                title = "Zeitschriften im Archiv Soziale Bewegungen",
                                subject = "Zeitschriften",
                                keywords = ("Neue Soziale Bewegungen",),
                                author = "Archiv Soziale Bewegungen e.V., 79098 Freiburg, Adlerstr. 12" )
        
        story = [Spacer(1,50 * mm)]
        style = self.styles["Normal"]
        
        story.append(Paragraph("Kürzel:", self.styles['h2']))
        self._print_field(story, "unvollständig", "F")
        self._print_field(story, "vollständig", "K")
        self._print_field(story, "beschädigte Exemplare", "B")
        self._print_field(story, "Sondernummern vorhanden", "S")

        story.append(Spacer(1,10 * mm))

        page_object = PageObject(self.zeitschriften_dao, Zeitschrift, ZeitschriftenFilter(), page_size=100)
        self.zeitschriften_dao.init_page_object(page_object)
        try:
            while True:
                for zeitschrift in page_object.objects:
                    story.append(Paragraph(zeitschrift.titel, self.styles['h2']))
                    if zeitschrift.untertitel is not None:
                        story.append(Paragraph(zeitschrift.untertitel, self.styles['h3']))
                        story.append(Spacer(1, 3 * mm))
                    story.append(Paragraph(zeitschrift.basic_info, style))
                    self.append_jahrgaenge(zeitschrift, story)
                    story.append(Spacer(1, 5 * mm))
                page_object.fetch_next()
        except DataError as e:
            pass
            
        doc.build(story, onFirstPage=self.first_page, onLaterPages=self.other_pages)
    
    def append_jahrgaenge(self, zeitschrift: Zeitschrift, story):
        
        for jahrgang in self.jahrgaenge_dao.fetch_jahrgaenge_for_zeitschrift(zeitschrift):
            story.append(Paragraph("%s" % jahrgang, self.styles['h4']))
            self._print_field(story, jahrgang.nummern, "Vorhanden")
            self._print_field(story, jahrgang.sondernummern, "Sondernummern")
    
    def first_page(self, canvas, doc):
        
        canvas.saveState()
        canvas.setFont('Times-Bold',45)
        canvas.drawCentredString(self.page_width/2.0, self.page_height-108, "Zeitschriften")
        canvas.setFont('Times-Bold',32)
        canvas.drawCentredString(self.page_width/2.0, self.page_height-150, "Archiv Soziale Bewegungen e.V.")
        canvas.drawCentredString(self.page_width/2.0, self.page_height-190, "Adlerstr.12, 79098 Freiburg")
        canvas.setFont('Times-Bold',16)
        canvas.drawCentredString(self.page_width/2.0, self.page_height-225, "Stand: %s" % date.today().strftime("%d. %B %Y"))

        canvas.setFont('Times-Roman',9)
        canvas.drawString(20 * mm , 15 * mm, "Zeitschriften im ASB, Seite 1")
        canvas.restoreState()
        
    def other_pages(self, canvas, doc):
        
        canvas.saveState()
        canvas.setFont('Times-Roman',9)
        canvas.drawString(20 * mm, 15 * mm, "Zeitschriften im ASB, Seite %d" % doc.page)
        canvas.restoreState()  
        
    def _print_field(self, story, value, definition):
        
        if value is None or value.strip() == '':
            return
        story.append(Paragraph("<b>%s:</b> %s" % (definition, value), self.styles['Normal']))        


@singleton
class Exporter:
    
    @inject
    def __init__(self, zeitschrifen_dao: ZeitschriftenDao,
                 broschueren_dao: BroschDao,
                 systematik_dao: SystematikDao,
                 broschueren_exporter: BroschuerenExporter,
                 zeitschriften_exporter: ZeitschriftenExporter,
                 cd_generation_engine: GenerationEngine):
        
        self.template_dir = path.join(path.dirname(__file__), "templates")
        self.zeitschriften_dao = zeitschrifen_dao
        self.broschueren_dao = broschueren_dao
        self.systmatik_dao = systematik_dao
        self.broschueren_exporter = broschueren_exporter
        self.zeitschriften_exporter = zeitschriften_exporter
        self.cd_generation_engine = cd_generation_engine
        self.outdir = "/var/www/html"
        self.pdfdir = path.join(self.outdir, "pdf")
        if not path.isdir(self.pdfdir):
            makedirs(self.pdfdir)
            
    
    def run(self):
        
        self.write_static()
        self.write_default_files()
        self.write_publikationen()
        #self.write_broschueren_pdf()
        #self.write_zeitschriften_pdf()
        
        #self.write_zeitschriften()
        #self.write_broschueren()
        self.write_vor_fuenf_jahren()
        
    def write_static(self):
        
        with zipfile.ZipFile(path.join(self.template_dir, "assets.zip"), 'r') as zip_ref:
            zip_ref.extractall(self.outdir)
        
    def write_default_files(self):
        
        file_bases = ("index", "news", "services", "bestaende", "coming-soon")
        
        for file_base in file_bases:
            template = self.load_full_template(file_base)
            file = open("%s/%s.html" % (self.outdir, file_base), "w")
            file.write(template)
            file.close()
            
    def write_publikationen(self):
        
        counter = 0
        cards = ""
        while True:
            counter += 1
            print("publikation%02d_card.template" % counter)
            if not path.exists(path.join(self.template_dir, "publikation%02d_card.template" % counter)):
                break
            cards += self.load_template("card", ("publikation%02d" % counter,))
            cards = cards.replace("@pubnr@", "%02d" % counter, 4)
            template = self.load_full_template("publikation%02d" % counter, "ecommerce", "ecommerce")
            self.write_html_file("publikation%02d.html" % counter, template)
            
        template = self.load_full_template("publikationen", "ecommerce", "ecommerce")
        template = template.replace("@cards@", cards)
        self.write_html_file("publikationen.html", template)
        
    def write_broschueren_pdf(self):
        
        self.broschueren_exporter.export(filename = path.join(self.pdfdir, "broschueren.pdf"))
        
    def write_zeitschriften_pdf(self):
        
        self.zeitschriften_exporter.export(filename = path.join(self.pdfdir, "zeitschriften.pdf"))
                
    def write_html_file(self, name, content):    
        
        file = open(path.join(self.outdir, name), "w")
        file.write(content)
        file.close()
        
    def write_zeitschriften(self):
        
        template = self.load_full_template("ztable", "table", "table")
        tablebody = self.create_ztable()
        template = template.replace("@tablebody@", tablebody)
        self.file = open("%s/ztable.html" % self.outdir, "w")
        self.file.write(template)
        self.file.close()
        
    def write_broschueren(self):
        
        template = self.load_full_template("btable", "table", "table")
        tablebody = self.create_btable()
        template = template.replace("@tablebody@", tablebody)
        self.file = open("%s/btable.html" % self.outdir, "w")
        self.file.write(template)
        self.file.close()
        
    def write_vor_fuenf_jahren(self):
 
        today = datetime.date.today()
        current_year = next_year = today.year - 50
        current_month = today.month
        next_month = current_month + 1
        if next_month == 13:
            next_month = 1
            next_year += 1
        export_info = ExportInfo()
        export_info.start_date = self.python_date_to_alexdate(datetime.date(current_year, current_month, 1))
        export_info.end_date = self.python_date_to_alexdate(datetime.date(next_year, next_month, 1) - datetime.timedelta(days=1))
        export_info.cd_name = "vor_fuenf_jahren"
        
        export_info.pagecontent['startpage'] = """
Der Monat vor 50 Jahren
=======================

Seit den 90er Jahren des vorigen Jahrhunderts baut das
Archiv soziale Bewegungen eine Datenbank auf, die
einerseits eine Chronologie der Bewegungsgeschichte im
Südwesten beinhaltet, andererseits eine Fülle digitalisierter
Dokumente, die mit dieser Chronologie verknüpft sind.

Hier zeigen wir immer die Einträge eines Monats, der
50 Jahre zurückliegt, aktuell also vom %s %s.

Klicken Sie auf <a href="#/events">Ereignisse</a> oder auf
<a href="#/documents">Dokumente</a> um in der Geschichte
von vor 50 Jahren zu stöbern.
        """ % (today.strftime("%B"), current_year)
        
        self.cd_generation_engine.run(export_info)
        
    def python_date_to_alexdate(self, date: datetime.date):
        
        return AlexDate(date.year, date.month, date.day)
        
    def load_full_template(self, name, assets_template=None, scripts_template=None):
        
        with open(path.join(self.template_dir, "header.template")) as template_file:
            template = template_file.read()
        with open(path.join(self.template_dir, "%s.template" % name)) as template_file:
            template += template_file.read()
        with open(path.join(self.template_dir, "footer.template")) as template_file:
            template += template_file.read()
        
        assets = self.load_template("assets", (assets_template, name))
        scripts = self.load_template("scripts", (scripts_template, name))
        
        template = template.replace('@additionalassets@', assets)
        template = template.replace('@additionalscripts@', scripts)
        
        return template
    
    def load_template(self, template_type, names):
        
        for name in names:
            if name is None:
                continue
            path_name = path.join(self.template_dir, "%s_%s.template" % (name, template_type))
            if path.exists(path_name):
                with open(path_name) as template_file:
                    template = template_file.read()
                return template
        return ""
    
    def create_ztable(self):
        
        tablebody = ""
        page_object = PageObject(self.zeitschriften_dao, Zeitschrift, ZeitschriftenFilter(), page_size=100)
        self.zeitschriften_dao.init_page_object(page_object)
        try:
            while True:
                for zeitschrift in page_object.objects:
                    print(zeitschrift.titel)
                    tablebody += "<tr><td>%s</td><td>%s</td></tr>\n" % (zeitschrift.titel, self.get_zeitsch_systematik_punkt(zeitschrift))
                page_object.fetch_next()
        except DataError as e:
            pass
        return tablebody

        return tablebody
    
    def create_btable(self):
        
        tablebody = ""
        page_object = PageObject(self.broschueren_dao, Brosch, BroschFilter(), page_size=100)
        self.broschueren_dao.init_page_object(page_object)
        try:
            while True:
                for broschuere in page_object.objects:
                    print(broschuere.titel)
                    tablebody += "<tr><td>%s</td><td>%s</td></tr>\n" % (broschuere.titel, self.get_brosch_systematik_punkt(broschuere))
                page_object.fetch_next()
        except DataError as e:
            pass
        return tablebody

    def get_brosch_systematik_punkt(self, broschuere: Brosch):
        
        syst_ids = self.broschueren_dao.fetch_systematik_ids(broschuere)
        if len(syst_ids) == 0:
            return "Unbekannt"
        else:
            systematik_node = self.systmatik_dao.fetch_by_id(syst_ids[0])
            root_node = self.systmatik_dao.fetch_root_node(systematik_node)
            return root_node.beschreibung
    
    def get_zeitsch_systematik_punkt(self, zeitschrift: Zeitschrift):
        
        syst_ids = self.zeitschriften_dao.fetch_systematik_ids(zeitschrift)
        if len(syst_ids) == 0:
            return "Unbekannt"
        else:
            systematik_node = self.systmatik_dao.fetch_by_id(syst_ids[0])
            root_node = self.systmatik_dao.fetch_root_node(systematik_node)
            return root_node.beschreibung
        
    
if __name__ == '__main__':
 
    locale.setlocale(locale.LC_TIME, "de_DE.UTF-8")    
    injector = Injector([AlexandriaDbModule, AlexBaseModule, CDExporterBasePluginModule, DaoModule, ServiceModule])
    
    exporter = injector.get(Exporter)
    exporter.run()