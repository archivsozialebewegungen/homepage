'''
Created on 02.02.2022

@author: michael
'''
from os import path, makedirs
from asb_zeitschriften.broschdaos import ZeitschriftenDao, Zeitschrift,\
    BroschDao, Brosch
from injector import Injector, inject, singleton
from asb_systematik.SystematikDao import AlexandriaDbModule, SystematikDao
import zipfile

@singleton
class Exporter:
    
    @inject
    def __init__(self, zeitschrifen_dao: ZeitschriftenDao, broschueren_dao: BroschDao, systematik_dao: SystematikDao):
        
        self.template_dir = path.join(path.dirname(__file__), "templates")
        self.zeitschriften_dao = zeitschrifen_dao
        self.broschueren_dao = broschueren_dao
        self.systmatik_dao = systematik_dao
        self.outdir = "/tmp/out"
        if not path.isdir(self.outdir):
            makedirs("/tmp/out")
    
    def run(self):
        
        self.write_static()
        self.write_default_files()
        #self.write_zeitschriften()
        #self.write_broschueren()
        
    def write_static(self):
        
        with zipfile.ZipFile(path.join(self.template_dir, "assets.zip"), 'r') as zip_ref:
            zip_ref.extractall(self.outdir)
        
    def write_default_files(self):
        
        file_bases = ("index", "news", "services", "bestaende", "publikationen", "coming-soon")
        
        for file_base in file_bases:
            template = self.load_full_template(file_base)
            file = open("%s/%s.html" % (self.outdir, file_base), "w")
            file.write(template)
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
        first_id = None
        zeitschrift = self.zeitschriften_dao.fetch_first(Zeitschrift())
        while first_id is None or zeitschrift.id != first_id:
            print(zeitschrift.titel)
            tablebody += "<tr><td>%s</td><td>%s</td></tr>\n" % (zeitschrift.titel, self.get_zeitsch_systematik_punkt(zeitschrift))
            if first_id is None:
                first_id = zeitschrift.id
            zeitschrift = self.zeitschriften_dao.fetch_next(zeitschrift)
        return tablebody
    
    def create_btable(self):
        
        tablebody = ""
        first_id = None
        broschuere = self.broschueren_dao.fetch_first(Brosch())
        while first_id is None or broschuere.id != first_id:
            print(broschuere.titel)
            tablebody += "<tr><td>%s</td><td>%s</td></tr>\n" % (broschuere.titel, self.get_brosch_systematik_punkt(broschuere))
            if first_id is None:
                first_id = broschuere.id
            broschuere = self.broschueren_dao.fetch_next(broschuere)
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
    
    injector = Injector([AlexandriaDbModule])
    
    exporter = injector.get(Exporter)
    exporter.run()