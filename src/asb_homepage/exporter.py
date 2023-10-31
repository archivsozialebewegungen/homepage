'''
Created on 02.02.2022

@author: michael
'''
from os import path, makedirs
from asb_zeitschriften.broschdaos import ZeitschriftenDao, Zeitschrift,\
    BroschDao, Brosch, PageObject, BroschFilter, ZeitschriftenFilter,\
    JahrgaengeDao, GenericFilter, BooleanFilterProperty, ZEITSCH_TABLE
from injector import Injector, inject, singleton
from asb_systematik.SystematikDao import AlexandriaDbModule, SystematikDao,\
    DataError, SystematikIdentifier
import zipfile
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus.doctemplate import SimpleDocTemplate
from reportlab.platypus.flowables import Spacer
from reportlab.lib.units import mm
from reportlab.platypus.paragraph import Paragraph
from reportlab.lib.pagesizes import A4
from datetime import date
import locale
from alexplugins.cdexporter.base import CDExporterBasePluginModule, ExportInfo,\
    GenerationEngine
import datetime
from alexandriabase import AlexBaseModule
from alexandriabase.daos import DaoModule
from alexandriabase.domain import AlexDate
from alexandriabase.services import ServiceModule
from asb_homepage.ButtonsExporter import ButtonsExporter
from pathlib import Path
from shutil import copyfile
import pysftp
from asb_homepage.InfoReader import NEWS_READER, InfoReaderModule,\
    PUBLICATION_READER
from asb_zeitschriften.guiconstants import FILTER_PROPERTY_SYSTEMATIK,\
    FILTER_PROPERTY_DIGITALISIERT
import os
from asb_homepage.SystematikExporter import SystematikExporter,\
    SystematikExporterModule
from alexandriabase.tools import PlakatExporter
from asb_homepage.PosterExporter import PosterExporter

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
        
    def export(self, filename="/tmp/zeitschriften.pdf", z_filter=None):
        
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
        self._print_field(story, "Digitalisiert", "D")

        story.append(Spacer(1,10 * mm))

        if z_filter is None:
            z_filter = ZeitschriftenFilter()
        page_object = PageObject(self.zeitschriften_dao, Zeitschrift, z_filter, page_size=100)
        self.zeitschriften_dao.init_page_object(page_object)
        try:
            while True:
                for zeitschrift in page_object.objects:
                    if zeitschrift.digitalisiert:
                        story.append(Paragraph("%s [D]" % zeitschrift.titel, self.styles['h2']))
                    else:
                        story.append(Paragraph(zeitschrift.titel, self.styles['h2']))
                    if zeitschrift.untertitel is not None:
                        story.append(Paragraph(zeitschrift.untertitel, self.styles['h3']))
                        story.append(Spacer(1, 3 * mm))
                    if zeitschrift.bemerkung is not None:
                        story.append(Paragraph(zeitschrift.bemerkung, style))
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
                 systematik_exporter: SystematikExporter,
                 buttons_exporter: ButtonsExporter,
                 plakat_exporter: PosterExporter,
                 news_reader: NEWS_READER,
                 publication_reader: PUBLICATION_READER,
                 cd_generation_engine: GenerationEngine):
        
        self.template_dir = path.join(path.dirname(__file__), "templates")
        self.zeitschriften_dao = zeitschrifen_dao
        self.broschueren_dao = broschueren_dao
        self.systmatik_dao = systematik_dao
        self.broschueren_exporter = broschueren_exporter
        self.zeitschriften_exporter = zeitschriften_exporter
        self.systematik_exporter = systematik_exporter
        self.buttons_exporter = buttons_exporter
        self.plakat_exporter = plakat_exporter
        self.news_reader = news_reader
        self.publication_reader = publication_reader
        self.cd_generation_engine = cd_generation_engine
        self.outdir = "/var/www/html"
        self.pdfdir = path.join(self.outdir, "pdf")
        self.imgdir = path.join(self.outdir, "img")
        if not path.isdir(self.pdfdir):
            makedirs(self.pdfdir)
        if not path.isdir(self.imgdir):
            makedirs(self.imgdir)
    
    def upload(self):
        
        with pysftp.Connection('ssh.strato.de', username='archivsozialebewegungen.de', password=os.environ['FTPPW'], port=22) as sftp:
            self.upload_dir(self.outdir, sftp)
        
    def upload_dir(self, directory, sftp):
        
        directory_path = Path(directory)
        for file in list(directory_path.iterdir()):
            if file.is_dir():
                try:
                    #print("Erstelle Verzeichnis %s" % file.name)
                    sftp.mkdir(file.name)
                except IOError:
                    pass
                with sftp.cd(file.name):
                    self.upload_dir(path.join(directory, file.name), sftp)
            else:
                #print("Lade Datei %s hoch" % file.name)
                sftp.put(path.join(directory, file.name))
    
    def run(self):
        
        self.write_static()
        self.write_default_files()
        self.write_index_file()
        
        self.write_publikationen()
        self.write_news()
        
        self.write_broschueren_pdf()
        self.write_zeitschriften_pdf()
        
        self.write_zeitschriften()
        self.write_broschueren()
        self.write_buttons_pdf()
        self.write_systematik_pdf()
        self.write_poster_pdf()
        self.write_vor_fuenf_jahren()
        
    def tiny_run(self):
        
        self.write_static()
        self.write_default_files()
        self.write_index_file()
        self.write_systematik_pdf()
        
        self.write_publikationen()
        self.write_news()
        
    def write_static(self):
        
        with zipfile.ZipFile(path.join(self.template_dir, "assets.zip"), 'r') as zip_ref:
            zip_ref.extractall(self.outdir)
        
        pdfdir = Path(path.join(self.template_dir, "pdf"))
        for file in list(pdfdir.glob('*.pdf')):
            copyfile(file, path.join(self.pdfdir, file.name))

        imgdir = Path(path.join(self.template_dir, "img"))
        for file in list(imgdir.glob('*')):
            copyfile(file, path.join(self.imgdir, file.name))
                
    def write_default_files(self):
        
        file_bases = ("services", "bestaende", "plakate", "buttons", "feministischesarchiv", "spenden", "history", "recherche", "fotos", "impressum", "coming-soon")
        
        for file_base in file_bases:
            template = self.load_full_template(file_base)
            file = open("%s/%s.html" % (self.outdir, file_base), "w")
            file.write(template)
            file.close()
    
    def write_index_file(self):

        template = self.load_full_template("index")
        template = template.replace("@news@", self.get_news_for_index_page())
        file = open("%s/index.html" % self.outdir, "w")
        file.write(template)
        file.close()
        
    def get_news_for_index_page(self):
        
        news = self.news_reader.read()
        news_html = ""
        for i in range(0, 3):
            template = self.load_template("news_item_short")
            news_item = news[-1-i]
            for section in news_item.keys():
                template = template.replace("@%s@" % section, news_item[section])
            news_html += template
        return news_html
            
    def write_publikationen(self):
        
        infos = self.publication_reader.read()
        cards = ""
        for idx in range(0, len(infos)):
            
            card = self.replace_sections(self.load_template("publikation_card"), infos[idx])
            card = self.insert_images(card, infos[idx]['images'])
            cards += card
            
            template = self.replace_sections(self.load_full_template("publikation", "ecommerce", "ecommerce"), infos[idx])
            template = self.insert_images(template, infos[idx]['images'])
            self.write_html_file("publikation-single-%03d.html" % (idx+1), template)
            
        template = self.load_full_template("publikationen", "ecommerce", "ecommerce")
        template = template.replace("@cards@", cards)
        self.write_html_file("publikationen.html", template)
    
    def insert_images(self, template, images):
        
        imagelist1 = ""
        imagelist2 = ""
        imagelist = images.split(":")
        for image in imagelist:
            imagelist1 += """<div class="card-image pcm-item">
                <img src="img/%s" alt="">
            </div>""" % image
            imagelist2 += """<div class="img-style pcth-item">
                <img src="img/%s" alt="">
            </div>""" % image
        return template.replace("@imagelist1@", imagelist1).\
            replace("@imagelist2@", imagelist2).\
            replace("@image@", imagelist[0])
 
    def write_news(self):
        
        template = self.load_full_template("news")
        
        articles = self.get_articles()
        
        template = template.replace("@articles@", articles)
        
        self.write_html_file("news.html", template)
        self.write_single_article_files()
        
    def write_single_article_files(self):
        
        news = self.news_reader.read()
        for i in range(0,len(news)):
            template = self.replace_sections(self.load_full_template("news-single"), news[i])
            self.write_html_file("news-single-%03d.html" % (i + 1), template)
    
    def replace_sections(self, template, info):
        
        for section in info.keys():
            template = template.replace("@%s@" % section, info[section].replace("\n\n", "</p><p>"))
        return template
    
    def get_articles(self):
        
        html = ""
        
        news = self.news_reader.read()
        for i in range(0,len(news)):
            template = self.replace_sections(self.load_template("news_item"), news[-1-i])
            template = template.replace('@link@', "news-single-%03d.html" % (len(news) - i))
            html += template
            
        return html
            
    def write_broschueren_pdf(self):
        
        self.broschueren_exporter.export(filename = path.join(self.pdfdir, "broschueren.pdf"))
        
    def write_zeitschriften_pdf(self):
        
        self.zeitschriften_exporter.export(filename = path.join(self.pdfdir, "zeitschriften.pdf"))
                
    def write_buttons_pdf(self):
        
        self.buttons_exporter.export(filename = path.join(self.pdfdir, "buttons.pdf"))
                
    def write_systematik_pdf(self):
        
        self.systematik_exporter.export(filename = path.join(self.pdfdir, "systematik.pdf"))
        
    def write_poster_pdf(self):
        
        self.plakat_exporter.export_to_pdf("%s/plakate.pdf" % self.pdfdir)
                
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
        
        assets = self._load_template_parts("assets", (assets_template, name))
        scripts = self._load_template_parts("scripts", (scripts_template, name))
        
        template = template.replace('@additionalassets@', assets)
        template = template.replace('@additionalscripts@', scripts)
        
        return template
    
    def _load_template_parts(self, template_type, names):
        
        for name in names:
            if name is None:
                continue
            path_name = path.join(self.template_dir, "%s_%s.template" % (name, template_type))
            if path.exists(path_name):
                with open(path_name) as template_file:
                    template = template_file.read()
                return template
        return ""
    
    def load_template(self, name):

        path_name = path.join(self.template_dir, "%s.template" % name)
        
        with open(path_name) as template_file:
            template = template_file.read()
    
        return template
    
    def create_ztable(self):
        
        tablebody = ""
        page_object = PageObject(self.zeitschriften_dao, Zeitschrift, ZeitschriftenFilter(), page_size=100)
        self.zeitschriften_dao.init_page_object(page_object)
        try:
            while True:
                for zeitschrift in page_object.objects:
                    #print(zeitschrift.titel)
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
                    #print(broschuere.titel)
                    tablebody += "<tr><td>%s</td><td>%s</td></tr>\n" % (broschuere.titel, self.get_brosch_systematik_punkt(broschuere))
                page_object.fetch_next()
        except DataError as e:
            pass
        return tablebody

    def get_brosch_systematik_punkt(self, broschuere: Brosch):
        
        #print(broschuere.hauptsystematik)
        systematik_node = self.systmatik_dao.fetch_by_identifier_object(SystematikIdentifier("%s" % broschuere.hauptsystematik))
        return systematik_node.beschreibung
    
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
    injector = Injector([InfoReaderModule, AlexandriaDbModule, AlexBaseModule, CDExporterBasePluginModule, DaoModule, ServiceModule, SystematikExporterModule])
    
    exporter = injector.get(Exporter)
    print("Starting build...")
    exporter.run()
    #exporter.tiny_run()
    print("Starting upload...")
    exporter.upload()
    print("Finished.")
    
    #z_filter = ZeitschriftenFilter()
    #z_filter.set_property_value(FILTER_PROPERTY_DIGITALISIERT, True)
    
    #exporter = injector.get(ZeitschriftenExporter)
    #exporter.export("/tmp/digitalisierte_zeitschriften.pdf", z_filter)
    
