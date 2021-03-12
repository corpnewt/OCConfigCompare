from Scripts import *
import os, plistlib, json, datetime, sys

try:
    long
    unicode
except NameError:  # Python 3
    long = int
    unicode = str

class OCCC:
    def __init__(self):
        self.d = downloader.Downloader()
        self.u = utils.Utils("OC Config Compare")
        if 2/3 == 0: self.dict_types = (dict,plistlib._InternalDict)
        else: self.dict_types = (dict)
        self.current_config = None
        self.current_plist  = None
        self.sample_plist   = None
        self.sample_url     = "https://github.com/acidanthera/OpenCorePkg/raw/{}/Docs/Sample.plist"
        self.opencorpgk_url = "https://api.github.com/repos/acidanthera/OpenCorePkg/releases"
        self.sample_path    = os.path.join(os.path.dirname(os.path.realpath(__file__)),os.path.basename(self.sample_url))
        self.settings_file  = os.path.join(os.path.dirname(os.path.realpath(__file__)),"Scripts","settings.json")
        self.settings       = {} # Smol settings dict - { "hide_with_prefix" : ["#"], "prefix_case_sensitive" : True }
        if os.path.exists(self.settings_file):
            try: self.settings = json.load(open(self.settings_file))
            except: pass
        self.sample_config  = self.sample_path if os.path.exists(self.sample_path) else None
        if self.sample_config:
            try:
                with open(self.sample_config,"rb") as f:
                    self.sample_plist = plist.load(f)
            except:
                self.sample_plist = self.sample_config = None

    def is_data(self, value):
        return (sys.version_info >= (3, 0) and isinstance(value, bytes)) or (sys.version_info < (3,0) and isinstance(value, plistlib.Data))

    def get_type(self, value):
        if isinstance(value, dict):
            return "Dictionary"
        elif isinstance(value, list):
            return "Array"
        elif isinstance(value, datetime.datetime):
            return "Date"
        elif self.is_data(value):
            return "Data"
        elif isinstance(value, bool):
            return "Boolean"
        elif isinstance(value, (int,long)):
            return "Integer"
        elif isinstance(value, float):
            return "Real"
        elif isinstance(value, (str,unicode)):
            return "String"
        else:
            return str(type(value))

    def compare(self):
        # First make sure we have plist info
        c = self.get_plist("user config.plist",self.current_config)
        if c is None:
            return
        self.current_config,self.current_plist = c
        # Get the latest release if we don't have one - or use the one we have
        if self.sample_config is None:
            s = self.get_latest(wait=False)
        else:
            s = self.get_plist("OC Sample.plist",self.sample_config)
        if s is None:
            return
        self.sample_config,self.sample_plist = s
        self.u.head()
        print("")
        print("Checking for values missing from User plist:")
        print("")
        changes = self.compare_value(self.sample_plist,self.current_plist,os.path.basename(self.current_config))
        if len(changes):
            print("\n".join(changes))
        else:
            print(" - Nothing missing from User config!")
        print("")
        print("Checking for values missing from Sample:")
        print("")
        changes = self.compare_value(self.current_plist,self.sample_plist,os.path.basename(self.sample_config))
        if len(changes):
            print("\n".join(changes))
        else:
            print(" - Nothing missing from Sample config!")
        print("")
        self.u.grab("Press [enter] to return...")

    def starts_with(self, value, prefixes):
        case_sensitive = self.settings.get("prefix_case_sensitive", True)
        if not case_sensitive: # Normalize case
            prefixes = tuple([x.lower() for x in prefixes]) if isinstance(prefixes,(list,tuple)) else prefixes.lower()
            value = value.lower()
        if isinstance(prefixes,list): prefixes = tuple(prefixes)
        return value.startswith(prefixes)

    def compare_value(self, compare_from, compare_to, path=""):
        change_list = []
        # Compare 2 collections and print anything that's in compare_from that's not in compare_to
        if type(compare_from) != type(compare_to):
            change_list.append("{} - Type Difference: {} --> {}".format(path,self.get_type(compare_to),self.get_type(compare_from)))
            return change_list # Can't compare further - they're not the same type
        if isinstance(compare_from,self.dict_types):
            # Let's compare keys
            not_keys = [x for x in list(compare_from) if not x in list(compare_to)]
            check_hide = self.settings.get("hide_with_prefix","#")
            if check_hide != None:
                if not isinstance(check_hide,(list,tuple)): check_hide = (check_hide,)
                not_keys = [x for x in not_keys if not self.starts_with(x,check_hide)]
            for x in not_keys:
                change_list.append("{} - Missing Key: {}".format(path,x))
            # Let's verify all other values if needed
            for x in list(compare_from):
                if x in not_keys: continue # Skip these as they're already not in the _to
                if check_hide != None and self.starts_with(x,check_hide): continue # Skipping this due to prefix
                val  = compare_from[x]
                val1 = compare_to[x]
                if type(val) != type(val1):
                    change_list.append("{} - Type Difference: {} --> {}".format(path+" -> "+x,self.get_type(val1),self.get_type(val)))
                    continue # Move forward as all underlying values will be different too
                if isinstance(val,list) or isinstance(val,self.dict_types):
                    change_list.extend(self.compare_value(val,val1,path+" -> "+x))
        elif isinstance(compare_from,list):
            # This will be tougher, but we should only check for dict children and compare keys
            if not len(compare_from) or not len(compare_to): return change_list # Nothing to do here
            if isinstance(compare_from[0],self.dict_types):
                # Let's compare keys
                change_list.extend(self.compare_value(compare_from[0],compare_to[0],path+" -> "+"Array"))
        return change_list

    def get_latest(self,use_release=True,wait=True):
        self.u.head()
        print("")
        if use_release:
            # Get the commitish
            try:
                urlsource = json.loads(self.d.get_string(self.opencorpgk_url,False))
                repl = urlsource[0]["target_commitish"]
            except: repl = "master" # fall back on the latest commit if failed
        else: repl = "master"
        dl_url = self.sample_url.format(repl)
        print("Gathering latest Sample.plist from:")
        print(dl_url)
        print("")
        p = None
        dl_config = self.d.stream_to_file(dl_url,self.sample_path)
        if not dl_config:
            print("\nFailed to download!\n")
            if wait: self.u.grab("Press [enter] to return...")
            return None
        print("Loading...")
        try:
            with open(dl_config,"rb") as f:
                p = plist.load(f)
        except Exception as e:
            print("\nPlist failed to load:  {}\n".format(e))
            if wait: self.u.grab("Press [enter] to return...")
            return None
        print("")
        if wait: self.u.grab("Press [enter] to return...")
        return (dl_config,p)

    def get_plist(self,plist_name="config.plist",plist_path=None):
        while True:
            if plist_path != None:
                m = plist_path
            else:
                self.u.head()
                print("")
                print("M. Return to Menu")
                print("Q. Quit")
                print("")
                m = self.u.grab("Please drag and drop the {} file:  ".format(plist_name))
                if m.lower() == "m":
                    return None
                elif m.lower() == "q":
                    self.u.custom_quit()
            plist_path = None # Reset
            pl = self.u.check_path(m)
            if not pl:
                self.u.head()
                print("")
                self.u.grab("That path does not exist!",timeout=5)
                continue
            try:
                with open(pl,"rb") as f:
                    p = plist.load(f)
            except Exception as e:
                self.u.head()
                print("")
                self.u.grab("Plist ({}) failed to load:  {}".format(os.path.basename(pl),e),timeout=5)
                continue
            return (pl,p) # Return the path and plist contents

    def print_hide_keys(self):
        hide_keys = self.settings.get("hide_with_prefix","#")
        if isinstance(hide_keys,(list,tuple)): return ", ".join(hide_keys)
        return hide_keys

    def custom_hide_prefix(self):
        self.u.head()
        print("")
        print("Key Hide Prefixes: {}".format(self.print_hide_keys()))
        print("")
        pref = self.u.grab("Please enter the custom hide key prefix:  ")
        return pref if len(pref) else None

    def remove_prefix(self):
        prefixes = self.settings.get("hide_with_prefix","#")
        if prefixes != None and not isinstance(prefixes,(list,tuple)):
            prefixes = [prefixes]
        while True:
            self.u.head()
            print("")
            print("Key Hide Prefixes:")
            print("")
            if prefixes == None or not len(prefixes):
                print(" - None")
            else:
                for i,x in enumerate(prefixes,start=1):
                    print("{}. {}".format(i,x))
            print("")
            print("A. Remove All")
            print("M. Prefix Menu")
            print("Q. Quit")
            print("")
            pref = self.u.grab("Please enter the number of the prefix to remove:  ").lower()
            if not len(pref): continue
            if pref == "m": return None if prefixes == None or not len(prefixes) else prefixes
            if pref == "q": self.u.custom_quit()
            if pref == "a": return None
            if prefixes == None: continue # Nothing to remove and not a menu option
            else: # Hope for a number
                try:
                    pref = int(pref)-1
                    assert 0 <= pref < len(prefixes)
                except:
                    continue
                del prefixes[pref]

    def hide_key_prefix(self):
        while True:
            self.u.head()
            print("")
            print("Key Hide Prefixes: {}".format(self.print_hide_keys()))
            print("")
            print("1. Hide Only Keys Starting With #")
            print("2. Hide comments (#), PciRoot, and most OC NVRAM samples")
            print("3. Add New Custom Prefix")
            print("4. Remove Prefix")
            print("5. Show All Keys")
            print("")
            print("M. Main Menu")
            print("Q. Quit")
            print("")
            menu = self.u.grab("Please select an option:  ")
            if menu.lower() == "m": return
            elif menu.lower() == "q": self.u.custom_quit()
            elif menu == "1":
                self.settings["hide_with_prefix"] = "#"
            elif menu == "2":
                self.settings["hide_with_prefix"] = ["#","PciRoot","4D1EDE05-","4D1FDA02-","7C436110-","8BE4DF61-"]
            elif menu == "3":
                new_prefix = self.custom_hide_prefix()
                if not new_prefix: continue # Nothing to add
                prefixes = self.settings.get("hide_with_prefix","#")
                if prefixes == None: prefixes = new_prefix # None set yet
                elif isinstance(prefixes,(list,tuple)): # It's a list or tuple
                    if new_prefix in prefixes: continue # Already in the list
                    prefixes = list(prefixes)
                    prefixes.append(new_prefix)
                else:
                    if prefixes == new_prefix: continue # Already set to that
                    prefixes = [prefixes,new_prefix] # Is a string, probably
                self.settings["hide_with_prefix"] = prefixes
            elif menu == "4":
                self.settings["hide_with_prefix"] = self.remove_prefix()
            elif menu == "5":
                self.settings["hide_with_prefix"] = None
            self.save_settings()

    def save_settings(self):
        try: json.dump(self.settings,open(self.settings_file,"w"),indent=2)
        except: pass

    def main(self):
        self.u.head()
        print("")
        print("Current Config:        {}".format(self.current_config))
        print("OC Sample Config:      {}".format(self.sample_config))
        print("Key Hide Prefixes:     {}".format(self.print_hide_keys()))
        print("Prefix Case-Sensitive: {}".format(self.settings.get("prefix_case_sensitive",True)))
        print("")
        print("1. Get Latest Release Sample.plist")
        print("2. Get Latest Commit Sample.plist")
        print("3. Select Local Sample.plist")
        print("4. Select Local User Config.plist")
        print("5. Change Key Hide Prefixes")
        print("6. Toggle Prefix Case-Sensitivity")
        print("7. Compare (will use latest Sample.plist if none selected)")
        print("")
        print("Q. Quit")
        print("")
        m = self.u.grab("Please select an option:  ").lower()
        if m == "q":
            self.u.custom_quit()
        elif m in ("1","2"):
            p = self.get_latest(use_release=m=="1")
            if p is not None:
                self.sample_config,self.sample_plist = p
        elif m == "3":
            p = self.get_plist("OC Sample.plist")
            if p is not None:
                self.sample_config,self.sample_plist = p
        elif m == "4":
            p = self.get_plist("user config.plist")
            if p is not None:
                self.current_config,self.current_plist = p
        elif m == "5":
            self.hide_key_prefix()
        elif m == "6":
            self.settings["prefix_case_sensitive"] = False if self.settings.get("prefix_case_sensitive",True) else True
            self.save_settings()
        elif m == "7":
            self.compare()

if __name__ == '__main__':
    if 2/3 == 0:
        input = raw_input
    o = OCCC()
    while True:
        try:
            o.main()
        except Exception as e:
            print("\nError: {}\n".format(e))
            input("Press [enter] to continue...")
