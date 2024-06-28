'''
Created on 05.10.2023

@author: michael
'''
from PIL import Image as PilImage
from injector import singleton, inject, Injector
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus.doctemplate import BaseDocTemplate, PageTemplate, \
    SimpleDocTemplate, NextPageTemplate
from reportlab.platypus.frames import Frame
from reportlab.platypus.paragraph import Paragraph

from alexandriabase import AlexBaseModule
from alexandriabase.daos import DocumentDao, DocumentFileInfoDao, DOCUMENT_TABLE, \
    DaoModule
from alexandriabase.services import DocumentFileManager, FileProvider, \
    ReferenceService, ServiceModule, THUMBNAIL, DocumentFileNotFound
from _io import BytesIO
from os.path import exists
from reportlab.platypus.flowables import Image, KeepTogether, PageBreak, Spacer
from alexandriabase.base_exceptions import NoSuchEntityException
from copy import deepcopy
from reportlab.lib.enums import TA_CENTER
from datetime import date
import locale
import os
from sqlalchemy.sql.expression import and_
from asb_systematik.SystematikDao import SystematikDao, SystematikIdentifier,\
    AlexandriaDbModule


styles = getSampleStyleSheet()

@singleton
class PosterExporter:
    
    @inject
    def __init__(self, dao: DocumentDao, 
                 file_info_dao: DocumentFileInfoDao, 
                 file_manager: DocumentFileManager, 
                 file_provider: FileProvider,
                 reference_service: ReferenceService):
        
        self.dao = dao
        self.file_info_dao = file_info_dao
        self.file_manager = file_manager
        self.file_provider = file_provider
        self.reference_service = reference_service
        self.titel = "Plakate im ASB"
        
        self.configure()
        
    def configure(self):

        pass        
               
    def export_to_pdf(self, filename=os.path.join("/", "tmp", "plakate.pdf")):
    
        doc = BaseDocTemplate(filename,
                              leftMargin = 1*cm,
                              rightMargin = 1*cm,
                              topMargin = 1*cm,
                              bottomMargin = 1*cm,
                              showBoundary=0)
        
        single_frame =  Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='single_col')

        #Two Columns
        frame1 = Frame(doc.leftMargin, doc.bottomMargin, doc.width/2-6, doc.height, id='col1')
        frame2 = Frame(doc.leftMargin+doc.width/2+6, doc.bottomMargin, doc.width/2-6, doc.height, id='col2')

        doc.addPageTemplates([PageTemplate(id='OneCol', frames=[single_frame]), PageTemplate(id='TwoCol',frames=[frame1,frame2])])
        
        styles['h1'].spaceBefore = 24
        
        title_style = deepcopy(styles['h1'])
        title_style.fontSize = 48
        title_style.leading = 48
        title_style.alignment = TA_CENTER
        date_style = deepcopy(title_style)
        date_style.fontSize = 24
        
        elements= [NextPageTemplate('OneCol')]
        elements.append(Spacer(0, 8*cm))
        elements.append(Paragraph(self.titel, title_style))
        elements.append(Spacer(0, 4*cm))
        elements.append(Paragraph("Stand: %s" % date.today().strftime("%d. %B %Y"), date_style))
        elements.append(NextPageTemplate('TwoCol'))
        elements.append(PageBreak())
        record_counter = 0
        for record in self.fetch_records():
            events = self.reference_service.get_events_referenced_by_document(record)
            elements += self.print_record(record, events)
            record_counter += 1
            #if record_counter == 10:
            #    break
            
        #print("Processed %d records." % record_counter)

        #start the construction of the pdf
        doc.build(elements)
        
    def print_record(self, record, events):
        
        if self.filtered(record, events):
            return
        
        main_elements = []
        main_elements.append(Paragraph("Dokument Nr.%d" % record.id, styles["h1"]))
        
        try:
            file_info = self.file_info_dao.get_by_id(record.id)
            file_name = self.file_manager.get_generated_file_path(file_info, THUMBNAIL)
            if not exists(file_name):
                print("Generating file %s" % file_name)
                self.file_provider.get_thumbnail(file_info)
        except DocumentFileNotFound:
            print("Problem mit Datensatz %d" % record.id)
            return main_elements
        except PermissionError:
            print("Rechteproblem mit Datensatz %d" % record.id)
            return main_elements
        except NoSuchEntityException:
            print("Objektproblem mit Datensatz %d" % record.id)
            return main_elements
        

        pil_image = PilImage.open(file_name, "r")
        width, height = pil_image.size
        catalog_size = 150, int(150 * (height/width))
        pil_image.thumbnail(catalog_size, PilImage.ANTIALIAS)
        img_stream = BytesIO()
        pil_image.save(img_stream, 'PNG')
        img_stream.seek(0)
        image = Image(img_stream)
        image.hAlign = "LEFT"
        main_elements.append(image)
        
        main_elements.append(Paragraph(record.description, styles['Normal']))
        
        if record.condition is not None and record.condition.strip() != "":
            main_elements.append(Paragraph("Zusätzliche Infos: %s" % record.condition))
        if record.doppel != 0:
            main_elements.append(Paragraph("Doppel vorhanden"))

        return [KeepTogether(main_elements), KeepTogether(self.print_events(events))]
    
    def print_events(self, events):
        
        elements = []
        if len(events) == 0:
            return elements
        if len(events) == 1:
            elements.append(Paragraph("Verknüpftes Ereignis", styles["h2"]))
        else:
            elements.append(Paragraph("Verknüpfte Ereignisse", styles["h2"]))
            
        for event in events:
            elements.append(Paragraph("<b>%s:</b> %s" % (event.daterange, event.description)))
        
        return elements             


    def fetch_records(self):

        condition = DOCUMENT_TABLE.c.doktyp == 9
        
        return self.dao.find(condition)
    
    def filtered(self, record, events):
        '''
        Returns True, if the record should be filtered out
        from the list. Override in subclasses.
        '''

        return False

    def print_img(self, id):    
        
        pass

@singleton
class PosterListExporter(PosterExporter):

    def fetch_records(self):

        try:
            condition = DOCUMENT_TABLE.c.hauptnr.in_(self.poster_list)
        except Exception as e:
            print("Please set field SystematikPunktExporter.poster_list to the poster ids you want to export.")
            raise e
        
        return self.dao.find(condition)


@singleton
class SystematikPunktExporter(PosterExporter):
    
    @inject
    def __init__(self, dao: DocumentDao, 
                 file_info_dao: DocumentFileInfoDao, 
                 file_manager: DocumentFileManager, 
                 file_provider: FileProvider,
                 reference_service: ReferenceService,
                 systematik_dao: SystematikDao):
        super().__init__(dao, file_info_dao, file_manager, file_provider, reference_service)
        self.systematik_dao = systematik_dao
    
    def export_posters_by_systematik(self, pdfdir:str):
        
        for syst_pkt in range(1,21):
            
            if syst_pkt == 18:
                continue
            self.hauptpunkt = syst_pkt
            self.titel = "Plakate für Systematikpunkt %d: %s" % (syst_pkt, self._fetch_text_for_syst_pkt(syst_pkt))
            self.export_to_pdf(os.path.join(pdfdir, "plakate%02d.pdf" % syst_pkt))

    def _fetch_text_for_syst_pkt(self, punkt):
        
        identifier = SystematikIdentifier("%d" % punkt)
        systematik_object = self.systematik_dao.fetch_by_identifier_object(identifier)
        return systematik_object.beschreibung

    def fetch_records(self):

        try:
            condition = and_(DOCUMENT_TABLE.c.doktyp == 9, 
                             DOCUMENT_TABLE.c.standort.like("%d%%" % self.hauptpunkt))
        except Exception as e:
            print("Please set field SystematikPunktExporter.hauptpunkt to the main systematik punkt.")
            raise e
        
        return self.dao.find(condition)
    
@singleton
class FormatExporter(PosterExporter):

    def fetch_records(self):

        try:
            condition = and_(DOCUMENT_TABLE.c.doktyp == 9, 
                             DOCUMENT_TABLE.c.aufbewahrung.ilike("%%%s%%" % self.format))
        except Exception as e:
            print("Please set field SystematikPunktExporter.format to the main systematik punkt.")
            raise e
        
        return self.dao.find(condition)

if __name__ == '__main__':

    #bauernkrieg_list = (7305, 7350, 10078, 12148, 12158, 19842, 19843, 19844, 19859, 19861, 20133, 20134, 23168, 26939, 27773, 27774, 28482, 29298, 26556)

    locale.setlocale(locale.LC_TIME, "de_DE.UTF-8")    

    injector = Injector([AlexBaseModule, DaoModule, ServiceModule, AlexandriaDbModule])

    #exporter = injector.get(FormatExporter)
    #exporter.titel = "Plakate A3"
    #exporter.poster_list = bauernkrieg_list
    #exporter.format = "a3"
    exporter = injector.get(SystematikPunktExporter)
    #exporter.hauptpunkt = 3
    #exporter.titel = "Plakate Antifaschistische Bewegungen"
    #exporter.export_to_pdf()
    exporter.export_posters_by_systematik("/tmp")