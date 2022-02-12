'''
Created on 08.02.2022

@author: michael
'''
from sqlalchemy.sql.schema import Table, MetaData, Column, ForeignKey
from sqlalchemy.sql.sqltypes import Integer, String, Date
from injector import Injector, Module, singleton, provider, inject
from sqlalchemy.engine.base import Engine, Connection
from sqlalchemy.engine.create import create_engine
import os
from sqlalchemy.sql.expression import select, and_

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4

PAGE_HEIGHT=A4[1]
PAGE_WIDTH=A4[0]


LINKS = 1
RECHTS = 2

RVF_METADATA = MetaData()

TONBAND_TABLE = Table(
    'tonband',
    RVF_METADATA,
    Column('tonband_id', Integer, primary_key=True, nullable=False),
    Column('nummer', Integer),
    Column('beschriftung', String),
    Column('beschr_spule', String),
    Column('hersteller', String),
    Column('kommentar', String),
)

SENDUNG_TABLE = Table(
    'sendung',
    RVF_METADATA,
    Column('sendungs_id', Integer, primary_key=True, nullable=False),
    Column('sendungsnr', Integer),
    Column('sendedatum', Date),
    Column('dateiname', String)
)

JOIN_TABLE = Table (
    'tonband_sendung',
    RVF_METADATA,
    Column('nummer', Integer, ForeignKey('tonband.tonband_id')),
    Column('sendungsnr', Integer, ForeignKey('sendung.sendungs_id'))
)

AUFNAHME_TABLE = Table(
    'aufnahme',
    RVF_METADATA,
    Column('aufnahme_id', Integer, primary_key=True, nullable=False),
    Column('tonband_id', Integer, ForeignKey('tonband.tonband_id')),
    Column('dateiname', String),
    Column('geschwindigkeit', String),
    Column('kanaele', Integer),
    Column('linkerkanal', Integer),
    Column('kommentar', String),
    Column('dauer', Integer)
)

def seconds_to_dauer(tsekunden: int):
    
    stunden = int(tsekunden / (60*60*1000))
    tsekunden -= stunden * 60 * 60 * 1000
    minuten = int(tsekunden / (60 * 1000))
    tsekunden -= minuten * 60 * 1000
    sekunden = int(tsekunden / 1000)
    tsekunden -= sekunden * 1000
    
    return "%d:%02d:%02d.%03d" % (stunden, minuten, sekunden, tsekunden) 

class Tonband():
    
    def __init__(self):
        self.id = None
        self.nummer = None
        self.beschriftung = None
        self.beschriftung_spule = None
        self.hersteller = None
        self.kommentar = None
        self.sendungen = []
        self.aufnahmen = []
        
class Sendung():
    
    def __init__(self):
        
        self.id = None
        self.nummer = None
        self.sendedatum = None
        self.dateiname = None
        
    def __str__(self):
        
        if self.nummer < 1:
            ausgabe = "Sendungsnr. unbekannt"
        else:
            ausgabe = "Sendung Nr.%d" % self.nummer
        if self.sendedatum is not None:
            ausgabe += " (%s)" % self.sendedatum
        return ausgabe
        
class Aufnahme():
    
    def __init__(self):
        
        self.base_path = "/srv/Rohscans/RVF"
        
        self.id = None
        self.tonband_id = None
        self.dateiname = None
        self.dauer = None
        self.kommentar = None
        self.kanaele = None
        self.kanal = None

    def __str__(self):
        
        ausgabe = "%s (%s" % (self.dateiname, self.dauer)
        if self.kanaele == 2:
            ausgabe += ", Stereo)" 
        elif self.kanal is None:
            ausgabe += ")"
        elif self.kanal == LINKS:
            ausgabe += ", linker Kanal)"
        else:
            ausgabe += ", rechter Kanal)"
        
        if self.kommentar is not None and self.kommentar.strip() != "":
            ausgabe += "\n   %s" % self.kommentar.replace("\n", "\n   ")
            
        if not os.path.exists(os.path.join(self.base_path, self.dateiname)):
            ausgabe += "\n   Datei nicht gefunden!"
        
        return ausgabe

@singleton
class AufnahmeDao():
    
    @inject
    def __init__(self, connection: Connection):
        
        self.connection = connection
        
    def fetch_for_tonband(self, tonband: Tonband):

        query = select([AUFNAHME_TABLE]).where(AUFNAHME_TABLE.c.tonband_id == tonband.id).order_by(AUFNAHME_TABLE.c.aufnahme_id)
        result = self.connection.execute(query)
        aufnahmen = []
        for row in result.fetchall():
            aufnahmen.append(self._row_to_object(row))
        return aufnahmen

    def _row_to_object(self, row) -> Aufnahme:
        
        obj = Aufnahme()
        obj.id = row[AUFNAHME_TABLE.c.aufnahme_id]
        obj.tonband_id  = row[AUFNAHME_TABLE.c.tonband_id]
        obj.dateiname  = row[AUFNAHME_TABLE.c.dateiname].replace('/danok/RVF/', '')
        obj.kanaele = row[AUFNAHME_TABLE.c.kanaele]
        obj.kommentar = row[AUFNAHME_TABLE.c.kommentar]
        obj.kanal = row[AUFNAHME_TABLE.c.linkerkanal]
        obj.dauer = seconds_to_dauer(row[AUFNAHME_TABLE.c.dauer])
        
        return obj
    
        
@singleton
class SendungDao():

    @inject
    def __init__(self, connection: Connection):
        
        self.connection = connection
        
    def fetch_for_tonband(self, tonband: Tonband):

        query = select([SENDUNG_TABLE, JOIN_TABLE]).where(and_(JOIN_TABLE.c.sendungsnr == SENDUNG_TABLE.c.sendungs_id,
                                                               JOIN_TABLE.c.nummer == tonband.id)).order_by(SENDUNG_TABLE.c.sendungsnr)
        result = self.connection.execute(query)
        sendungen = []
        for row in result.fetchall():
            sendungen.append(self._row_to_object(row))
        return sendungen
            
    def _row_to_object(self, row):
        
        obj = Sendung()
        obj.id = row[SENDUNG_TABLE.c.sendungs_id]
        obj.nummer = row[SENDUNG_TABLE.c.sendungsnr]
        obj.sendedatum = row[SENDUNG_TABLE.c.sendedatum]
        obj.dateiname = row[SENDUNG_TABLE.c.dateiname]
        return obj

@singleton        
class TonbandDao():
    
    @inject
    def __init__(self, connection: Connection, sendung_dao: SendungDao, aufnahme_dao: AufnahmeDao):
        
        self.connection = connection
        self.sendung_dao = sendung_dao
        self.aufnahme_dao = aufnahme_dao
        
    def fetch_all(self):
        
        query = select([TONBAND_TABLE]).order_by(TONBAND_TABLE.c.nummer)
        result = self.connection.execute(query)
        baender = []
        for row in result.fetchall():
            band = self._row_to_object(row)
            band.sendungen = self.sendung_dao.fetch_for_tonband(band)
            band.aufnahmen = self.aufnahme_dao.fetch_for_tonband(band)
            baender.append(band)
        return baender
    
    def _row_to_object(self, row):
        
        obj = Tonband()
        obj.id = row[TONBAND_TABLE.c.tonband_id]
        obj.nummer = row[TONBAND_TABLE.c.nummer]
        obj.beschriftung = row[TONBAND_TABLE.c.beschriftung]
        obj.beschriftung_spule = row[TONBAND_TABLE.c.beschr_spule]
        obj.hersteller = row[TONBAND_TABLE.c.hersteller]
        obj.kommentar = row[TONBAND_TABLE.c.kommentar]
        return obj

@singleton
class RvfExporter():
    
    @inject
    def __init__(self, tonband_dao: TonbandDao):
        
        self.tonband_dao = tonband_dao
        self.styles = getSampleStyleSheet()
        
    def export(self, filename="/tmp/rvf.pdf"):
        
        doc = SimpleDocTemplate(filename, 
                                title = "Radio Verte Fessenheim Bänder im Archiv Soziale Bewegungen",
                                subject = "Radio Verte Fessenheim",
                                keywords = ("Radio Verte Fessenheim", "RVF", "Radio Dreyeckland", "RDL"),
                                author = "Archiv Soziale Bewegungen e.V., 79098 Freiburg, Adlerstr. 12" )
        
        story = [Spacer(1,50 * mm)]
        style = self.styles["Normal"]
        
        for band in self.tonband_dao.fetch_all():
            
            story.append(Paragraph("Band Nr.%d" % band.nummer, self.styles['h1']))
            story.append(Spacer(1, 3 * mm))
            
            self._add_field(story, band.beschriftung, "Beschriftung")
            self._add_field(story, band.beschriftung_spule, "Beschriftung Spule")
            self._add_field(story, band.hersteller, "Hersteller")
            self._add_field(story, band.kommentar, "Kommentar")
            

            if len(band.sendungen) > 0:            
                story.append(Paragraph("Sendungen:", self.styles['h2']))
                story.append(Spacer(1, 3 * mm))

                for sendung in band.sendungen:
                    story.append(Paragraph("   %s" % sendung, style))
            
            if len(band.aufnahmen) > 0:
                story.append(Paragraph("Aufnahmen:", self.styles['h2']))
                story.append(Spacer(1, 3 * mm))

                for aufnahme in band.aufnahmen:
                    story.append(Paragraph("   %s" % aufnahme, style))
            
            story.append(Spacer(1, 6 * mm))

        doc.build(story, onFirstPage=self.first_page, onLaterPages=self.other_pages)
    
    def _add_field(self, story, value, definition):
        
        if value is None or value.strip() == '':
            return
        story.append(Paragraph("<b>%s:</b> %s" % (definition, value), self.styles["Normal"]))
        story.append(Spacer(1, 3 * mm))

    def first_page(self, canvas, doc):
        
        canvas.saveState()
        canvas.setFont('Times-Bold',45)
        canvas.drawCentredString(PAGE_WIDTH/2.0, PAGE_HEIGHT-108, "Radio Verte Fessenheim")
        canvas.setFont('Times-Bold',32)
        canvas.drawCentredString(PAGE_WIDTH/2.0, PAGE_HEIGHT-150, "Die Bänder im Archiv")
        canvas.drawCentredString(PAGE_WIDTH/2.0, PAGE_HEIGHT-180, "soziale Bewegungen")

        canvas.setFont('Times-Roman',9)
        canvas.drawString(20 * mm , 15 * mm, "Bänder RVF, Seite 1")
        canvas.restoreState()
        
    def other_pages(self, canvas, doc):
        
        canvas.saveState()
        canvas.setFont('Times-Roman',9)
        canvas.drawString(20 * mm, 15 * mm, "Bänder RVF, Seite %d" % doc.page)
        canvas.restoreState()  
        
    def export_console(self):
        
        for band in self.tonband_dao.fetch_all():
            print("Band Nr.%d" % band.nummer)
            self._print_field(band.beschriftung, "Beschriftung")
            self._print_field(band.beschriftung_spule, "Beschriftung Spule")
            self._print_field(band.hersteller, "Hersteller")
            self._print_field(band.kommentar, "Kommentar")
            print("Sendungen:")
            for sendung in band.sendungen:
                print("   %s" % sendung)
            print("Aufnahmen:")
            for aufnahme in band.aufnahmen:
                print("   %s" % aufnahme)
            print("-----------------------------------------")
    
    def _print_field(self, value, definition):
        
        if value is None or value.strip() == '':
            return
        print("%s: %s" % (definition, value))        

class RvfDbModule(Module):
    
    @singleton
    @provider
    def provide_engine(self) -> Engine:
        return create_engine(os.environ['RVF_DB_URL'])

    @singleton
    @provider
    @inject
    def provide_connection(self, engine: Engine) -> Connection:
        return engine.connect()
    

if __name__ == '__main__':
    
    injector = Injector([RvfDbModule])
    exporter = injector.get(RvfExporter)
    exporter.export()