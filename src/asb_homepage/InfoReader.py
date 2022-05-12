'''
Created on 28.02.2022

@author: michael
'''
from os import path
from injector import Module, provider, BoundKey

NEWS_READER = BoundKey('news_reader')
PUBLICATION_READER = BoundKey('publication_reader')

class InfoReader():
    
    def __init__(self, info_type, sections):
        
        self.type = info_type
        self.sections = sections
        
        
    def read(self):

        info_dir = path.join(path.dirname(__file__), "templates", self.type)
        
        index = 0
        infos = []
        while True:
            index += 1
            file_name = path.join(info_dir, "%s%03d.info" % (self.type, index))
            if not path.exists(file_name):
                break
            infos.append(self.read_infos(index, file_name))
        return infos
                             
    def read_infos(self, index, filename):
        
        section_idx = 0
        item = {}
        item[self.sections[0]] = ""
        item['link'] = "%s-single-%03d.html" % (self.type, index)
            
        with open(filename) as news_file:
            for line in news_file.readlines():
                if line.strip() == "" and section_idx < len(self.sections) - 1:
                    item[self.sections[section_idx]] = item[self.sections[section_idx]][:-1]  
                    section_idx += 1
                    item[self.sections[section_idx]] = ""
                else:
                    item[self.sections[section_idx]] += line
            
        return item
        
class InfoReaderModule(Module):
    
    @provider
    def news_reader_provider(self) -> NEWS_READER:
        
        return InfoReader('news', ('image', "heading", "date", "author", "shortteaser", "teaser", "text"))        


    @provider
    def publication_reader_provider(self) -> PUBLICATION_READER:
        
        return InfoReader('publikation', ('images', "title", "type", "price", "inventory", "badge", "teaser", "text"))        
