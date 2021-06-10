import argparse
import requests
import json
import shutil
import os
import os.path
import git 
import zipfile
import tarfile
import gzip
from html.parser import HTMLParser
from html.entities import name2codepoint


links = []
class HtmlParser(HTMLParser):
    
    def handle_starttag(self, tag, attrs):
        if(tag != 'a'):
            return 
        links.append(dict(attrs)['href'])

class Log:
        
    def sys(self, msg, ident = 0):
        self.write('-', msg, ident)

    def info(self, msg, ident = 0):
        self.write('I', msg, ident)

    def warn(self, msg, ident = 0):
        self.write('W', msg, ident)

    def error(self, msg, ident = 0):
        self.write('E', msg, ident)

    def write(self, level, msg, ident):
        lvl = '|' + level + '|'
        if ident > 0:
            for i in ident:
                lvl + "\t"
        print(lvl + msg)        

class Git():
    def __init__(self, base_dir):
        self.log = Log()
        self.base_dir = base_dir
        

        
class Cli:
    def __init__(self):
        self.log = Log()
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def load_cfg(self):
        f = open('config.json',)
        self.conf = json.load(f)
        f.close()

        self.dev_img_name = self.conf['build']['dev_image']
        self.vm_dir = self.conf['base']['vm_dir']
        self.base_vm = self.base_dir + self.vm_dir + '/'
        self.path = self.base_dir + '/' + self.vm_dir + '/image'
        self.arch = self.conf['build']['arch']
        self.img_file = self.conf['cog']['base' + self.arch] + '.image'

    def checkout_deps(self):
        self.log.sys('Checking up dependencies')
        for d in self.conf['deps']:
            if not 'target' in d:
                d['target'] = d['dir']
            target = self.base_dir + '/' + d['target']
            self.log.info('Found target:' + target)
            d['target'] = target
            self.log.info('Updating dep: ' + target)
            if not os.path.exists(target):
                self.log.info('Target directory not found')
                self.clone(d)
            else:
                self.log.info('Target directory found')
                self.checkout(d)

    def clone(self, dep):
        self.log.info('Cloning dependency: ' + dep['name'])
        self.log.info("\tfrom -> " + dep['repo_url'])
        self.log.info("\tinto -> " + dep['target'])
        self.log.info("\tbranch -> " + dep['branch'])
        git.Git(dep['target']).clone(dep['repo_url'])
        #Repo.clone_from(dep['repo_url'], dep['target'])
        
    def checkout(self, dep):
        self.log.info('Pulling changes for: ' + dep['name'])
        self.log.info("\tfrom -> " + dep['repo_url'])
        self.log.info("\tinto -> " + dep['target'])
        self.log.info("\tbranch -> " + dep['branch'])
        g = git.cmd.Git(dep['target'])
        g.checkout()
        #Repo.clone_from(dep['repo_url'], dep['target'])

    def check_comp_file(self):
        self.log.sys("Checking Nopsys compilation file")
        if not os.path.exists(self.base_dir + "/nopsys/compilation.conf"):

            if os.path.exists(self.base_dir + "/nopsys/compilation.conf.example"):
                shutil.copyfile(
                    self.base_dir + "/nopsys/compilation.conf.example", 
                    self.base_dir + "/nopsys/compilation.conf")
                
                self.log.warn("\tYou should review the compilation configuration file")
                self.log.warn("\tlocated at:" + self.base_dir + "/nopsys/compilation.conf")
                self.log.warn("\tto make sure all tools and paths are property referenced")
            else:
                self.log.info("not found Nopsys compilation file, compilation.conf.example")    
        else:
            self.log.info("Found Nopsys compilation file, skipping")

    def gunzip(self, source_filepath, dest_filepath, block_size=65536):
        with gzip.open(source_filepath, 'rb') as s_file, \
                open(dest_filepath, 'wb') as d_file:
            shutil.copyfileobj(s_file, d_file, block_size)
            
    def getSqueakSources(self):
        self.log.sys("Checking for SqueakV50.sources file")
        sqsrc = self.path + '/SqueakV50.sources'
        if not os.path.exists(sqsrc):
            self.log.info("Squeak sources file not found in : " + sqsrc)
            squrl = self.conf['cog']['squeak_src']

            filename = self.download(squrl, self.path + '/')
            self.gunzip(sqsrc + ".gz", sqsrc)
            self.log.info("Squeak sources file extracted to : " + sqsrc)
        else:
            self.log.info("Squeak sources already present, skipping")

    def getGoodTrunkVM(self):
        vm_dir = self.conf['base']['vm_dir']
        path = self.base_dir + '/' + vm_dir + '/image'
        
        self.log.sys('Fetching releases')
        url = requests.get(self.conf['cog']['releases'])
        releases = json.loads(url.text)
        cog_pkg = self.conf['cog']

        release = releases[0]
        self.log.info( release['tag_name'] + ' > ' + release['target_commitish'] )
        pkg_name = cog_pkg['volume'] + "_" + cog_pkg['platform'] + "_" + release['tag_name'] 
        pkg_file = pkg_name + ".tar.gz"
        pkg = ''
        
        for asset in release['assets']:
            if asset['name'] == pkg_file:
                self.log.info('Found: ' + asset['name'])
                pkg = asset

        if pkg == '':
            self.log.info('Specified release not found')    
        
        filename = self.download(pkg['browser_download_url'], path)
        dest_folder = path + "/" +  pkg_name
        
        self.log.info('Extracting to : ' + dest_folder)
        targzfile =  tarfile.open(path + "/" + filename)
        targzfile.extractall(self.path)
        targzfile.close()
        src = self.path + "/sqcogspur64linuxht"

        file_names = os.listdir(src)
        for file_name in file_names:
            self.log.info('Moving: ' + file_name + ' to : ' + self.path)
            try:
                shutil.move(src + '/'+ file_name , self.path)
            except OSError as e:
                self.log.error("Can't move: %s" % (e))

    def getLatestSqueakVersion(self):
        parser = HtmlParser()
        parser.links = []
        self.log.sys('Checking for latest Spur image')
        img_src = self.conf['cog']['squeak_img_src']
        if not os.path.exists(self.path + '/' + self.img_file):
            self.log.info(self.path + '/' + self.img_file)
            r = requests.get(img_src)
            parser.feed(str(r.content))

            if len(links) > 0:
                links.sort()
                latest = links[-1]
                #self.latest = latest
                img_url = img_src + "/" + latest + latest[:-1] + ".zip"
                self.log.info("Found : " + latest[:-1])
                self.download(img_url, self.path)
                file_path = self.path + '/' + latest[:-1]
                return latest[:-1]
            else:
                self.log.info("No Squeak suitable version found")
        else:
            self.log.info("Squeak Image found, skipping")
        
        return None

    def getLatestTrunkImg(self):   
        latest = self.getLatestSqueakVersion()
        if not latest is None:
            download = self.path + '/' + latest + '.zip'

            self.log.info('Extracting to : ' + self.path)
            with zipfile.ZipFile(download, 'r') as zip_ref:
                zip_ref.extractall(self.path)
            chg_name = self.conf['cog']['base' + self.arch] + '.changes'
            self.log.info("Renaming: " + latest + '.image to: ' + self.img_file)
            os.rename(self.path + '/' + latest + '.image', self.path + "/" + self.img_file)
            self.log.info("Renaming: " + latest + '.changes to: ' + chg_name)
            os.rename(self.path + '/' + latest + '.changes', self.path + "/" + chg_name )   

    def download(self, url: str, dest_folder: str):
        self.log.sys('Downloading from: ' + url)
        if not os.path.exists(dest_folder):
            os.makedirs(dest_folder)  # create folder if it does not exist

        filename = url.split('/')[-1].replace(" ", "_")  # be careful with file names
        file_path = os.path.join(dest_folder, filename)

        r = requests.get(url, stream=True)
        if r.ok:
            self.log.info("Saving to: " + file_path)
            with open(file_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024 * 8):
                    if chunk:
                        f.write(chunk)
                        f.flush()
                        os.fsync(f.fileno())
        else:  # HTTP status code 4XX/5XX
            self.log.error("Download failed: status code {}\n{}".format(r.status_code, r.text))

        return filename

    def updateImg(self):
        self.log.info("Updating image..")
        lib = self.path + '/lib/squeak'
        file_names = os.listdir(lib)
        src_file = '/SqueakV50.sources'
        dest = lib + '/' + file_names[0] + src_file
        if not os.path.exists(dest):
            self.log.info("Moving: " + src_file + ' to: ' + dest )
            try:
                shutil.move(self.path + src_file  , lib + '/' + file_names[0] )
            except OSError as e:
                self.log.error("Can't move: %s" % (e))

        self.log.sys("Launching image now..")
        vm = self.path + '/squeak '
        img = self.path + '/' + self.img_file
        command =  vm + img + ' ' + self.path + '/NukePreferenceWizardMorph.st' 
        self.log.info("Using command:" + command)
        res = os.system(command)
        if res == 1:
            self.log.info("Relaunching..")
            try:
                chg_name = self.conf['cog']['base' + self.arch] + '.changes'
                os.rename(file_path + '.image', self.path + "/" + self.img_file)
                os.rename(file_path + '.changes', self.path + "/" + chg_name )
                
            except OSError as e:
                self.log.error("Can't move: %s" % (e))

        else:
            self.log.error("An error ocurred, please check your config..")

    def buildVMMakerImage(self):
        self.log.sys("Building VMMaker..")
        vm = self.path + '/squeak '
        img = self.path + '/' + self.img_file
        command =  vm + img + ' ' + self.path + '/BuildSqueakSpurTrunkVMMakerImage.st' 
        self.log.info("Using command:" + command)
        res = os.system(command)
        if res != 1:
            self.log.error("An error ocurred while building VMMaker..")

    def run(self):
        print("\n-----------------------")
        print("CogNos installer script")
        print("-----------------------\n")
        self.log.info("Using base dir: " + self.base_dir)
        self.load_cfg()
        self.check_comp_file()
        self.checkout_deps()
        self.getGoodTrunkVM()
        self.getSqueakSources()
        self.getLatestTrunkImg()
        self.updateImg()
        self.buildVMMakerImage()
        self.log.info("Setup Done!")

c = Cli()
c.run()
                    