from Scripts import *
import os, plistlib, json, datetime, sys, argparse, copy, datetime, shutil

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
        self.w = 80
        self.h = 24
        if os.name == "nt":
            self.w = 120
            self.h = 30
        self.current_config = None
        self.current_plist  = None
        self.sample_plist   = None
        self.sample_url     = "https://github.com/acidanthera/OpenCorePkg/raw/{}/Docs/Sample.plist"
        self.opencorpgk_url = "https://api.github.com/repos/acidanthera/OpenCorePkg/releases"
        self.sample_path    = os.path.join(os.path.dirname(os.path.realpath(__file__)),os.path.basename(self.sample_url))
        self.settings_file  = os.path.join(os.path.dirname(os.path.realpath(__file__)),"Scripts","settings.json")
        self.settings       = {} 
        """Smol default settings dict = {
            "hide_with_prefix"      : ["#"],
            "prefix_case_sensitive" : True,
            "suppress_warnings"     : False,
            "update_user"           : False,
            "update_sample"         : False,
            "no_timestamp"          : False,
            "backup_original"       : False,
            "resize_window"         : True
        }"""
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

    def get_timestamp(self,name="config.plist",backup=False):
        needs_plist = name.lower().endswith(".plist")
        if needs_plist: name = name[:-6] # Strip the .plist extension
        name = "{}-{}{}".format(name,"backup-" if backup else "",datetime.datetime.today().strftime("%Y-%m-%d-%H.%M"))
        if needs_plist: name += ".plist" # Add it to the end again
        return name

    def compare(self,hide=False):
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
        if not hide:
            self.u.head()
            print("\nGathering differences...")
        p_string = ""
        p_string += "\nChecking for values missing from User plist:\n\n"
        user_copy = copy.deepcopy(self.current_plist) if self.settings.get("update_user",False) else None
        user_missing = self.compare_value(self.sample_plist,self.current_plist,path=os.path.basename(self.current_config),to_copy=user_copy!=None,compare_copy=user_copy)
        p_string += "\n".join(user_missing) if len(user_missing) else " - Nothing missing from User config!"
        p_string += "\n\nChecking for values missing from Sample:\n\n"
        sample_copy = copy.deepcopy(self.sample_plist) if self.settings.get("update_sample",False) else None
        sample_missing = self.compare_value(self.current_plist,self.sample_plist,path=os.path.basename(self.sample_config),to_copy=sample_copy!=None,compare_copy=sample_copy)
        p_string += "\n".join(sample_missing) if len(sample_missing) else " - Nothing missing from Sample config!"
        p_string += "\n"
        for l,c,p in ((user_missing,user_copy,self.current_config),(sample_missing,sample_copy,self.sample_config)):
            if c!=None and len([x for x in l if not x.lower().endswith(": skipped")]):
                path = os.path.dirname(p)
                name = os.path.basename(p)
                if self.settings.get("backup_original",False):
                    backup_name = self.get_timestamp(name,backup=True)
                    p_string += "\nBacking up {} -> {}...".format(name,backup_name)
                    shutil.copy(p,os.path.join(path,backup_name))
                elif not self.settings.get("no_timestamp",False):
                    name = self.get_timestamp(name)
                p_string += "\nUpdating {} with changes...".format(name)
                try:
                    with open(os.path.join(path,name),"wb") as f:
                        plist.dump(c,f)
                except Exception as e:
                    p_string += "\nError saving {}: {}".format(name,str(e))
                p_string += "\n"
        w = max([len(x) for x in p_string.split("\n")])+1
        h = 5 + len(p_string.split("\n"))
        if self.settings.get("resize_window",True): self.u.resize(w if w > self.w else self.w, h if h > self.h else self.h)
        if not hide:
            if self.settings.get("resize_window",True): self.u.resize(w if w > self.w else self.w, h if h > self.h else self.h)
            self.u.head()
        print(p_string)
        if not hide: self.u.grab("Press [enter] to return...")

    def starts_with(self, value, prefixes=None):
        if prefixes is None: prefixes = self.settings.get("hide_with_prefix","#")
        if prefixes is None: return False # Nothing passed, and nothing in settings - everything is allowed
        case_sensitive = self.settings.get("prefix_case_sensitive",True)
        if not case_sensitive: # Normalize case
            prefixes = [x.lower() for x in prefixes] if isinstance(prefixes,(list,tuple)) else prefixes.lower()
            value = value.lower()
        if isinstance(prefixes,list): prefixes = tuple(prefixes) # Convert to tuple if need be
        if not isinstance(prefixes,tuple): prefixes = (prefixes,) # Wrap up in tuple as needed
        return value.startswith(prefixes)

    def get_valid_keys(self, check_dict):
        return [x for x in check_dict if not self.starts_with(x,prefixes=None)]

    def compare_value(self, compare_from, compare_to, to_copy = False, compare_copy = None, path=""):
        change_list = []
        # Compare 2 collections and print anything that's in compare_from that's not in compare_to
        if type(compare_from) != type(compare_to): # Should only happen if it's top level differences
            change_list.append("{} - Type Difference: {} --> {}".format(path,self.get_type(compare_to),self.get_type(compare_from)))
        elif isinstance(compare_from,self.dict_types):
            # Let's compare keys
            not_keys = self.get_valid_keys([x for x in list(compare_from) if not x in list(compare_to)])
            for x in not_keys:
                if to_copy: compare_copy[x] = compare_from[x]
                change_list.append("{} - Missing Key: {}".format(path,x))
            # Let's verify all other values if needed
            for x in list(compare_from):
                if x in not_keys: continue # Skip these as they're already not in the _to
                if self.starts_with(x): continue # Skipping this due to prefix
                if type(compare_from[x]) != type(compare_to[x]):
                    if to_copy: compare_copy[x] = compare_from[x]
                    change_list.append("{} - Type Difference: {} --> {}".format(path+" -> "+x,self.get_type(compare_to[x]),self.get_type(compare_from[x])))
                    continue # Move forward as all underlying values will be different too
                if isinstance(compare_from[x],list) or isinstance(compare_from[x],self.dict_types):
                    change_list.extend(self.compare_value(compare_from[x],compare_to[x],path=path+" -> "+x,to_copy=to_copy,compare_copy=compare_copy[x] if to_copy else None))
        elif isinstance(compare_from,list):
            # This will be tougher, but we should only check for dict children and compare keys
            if not len(compare_from) or not len(compare_to):
                if not self.settings.get("suppress_warnings"): change_list.append(path+" -> {}-Array - Empty: Skipped".format("From|To" if not len(compare_from) and not len(compare_to) else "From" if not len(compare_from) else "To"))
            elif not all((isinstance(x,self.dict_types) for x in compare_from)):
                if not self.settings.get("suppress_warnings"): change_list.append(path+" -> From-Array - Non-Dictionary Children: Skipped")
            else:
                # All children of compare_from are dicts - let's ensure consistent keys
                valid_keys = []
                for x in compare_from: valid_keys.extend(self.get_valid_keys(x))
                valid_keys = set(valid_keys)
                global_keys = []
                for key in valid_keys:
                    if all((key in x for x in compare_from)): global_keys.append(key)
                global_keys = set(global_keys)
                if not global_keys:
                    if not self.settings.get("suppress_warnings"): change_list.append(path+" -> From-Array - All Child Keys Differ: Skipped")
                else:
                    if global_keys != valid_keys:
                        if not self.settings.get("suppress_warnings"): change_list.append(path+" -> From-Array - Child Keys Differ: Checking Consistent")
                        # Build a key placeholder to check using only consistent keys
                        compare_placeholder = {}
                        for key in global_keys: compare_placeholder[key] = compare_from[0][key]
                    else:
                        # Fall back on compare_from[0]
                        compare_placeholder = compare_from[0]
                    # Compare keys, pull consistent placeholders from compare_placeholder
                    for i,check in enumerate(compare_to):
                        change_list.extend(self.compare_value(compare_placeholder,compare_to[i],path=path+" -> Array[{}]".format(i),to_copy=to_copy,compare_copy=compare_copy[i] if to_copy else None))
        return change_list

    def get_latest(self,use_release=True,wait=True,hide=False):
        if not hide:
            if self.settings.get("resize_window",True): self.u.resize(self.w,self.h)
            self.u.head()
            print("")
        if use_release:
            # Get the tag name
            try:
                urlsource = json.loads(self.d.get_string(self.opencorpgk_url,False))
                repl = urlsource[0]["tag_name"]
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
        if self.settings.get("resize_window",True): self.u.resize(self.w,self.h)
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
            print("6. Toggle Suppress Warnings (Currently {})".format(self.settings.get("suppress_warnings",False)))
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
            elif menu == "6":
                self.settings["suppress_warnings"] = not self.settings.get("suppress_warnings",False)
            self.save_settings()

    def save_settings(self):
        try: json.dump(self.settings,open(self.settings_file,"w"),indent=2)
        except: pass

    def main(self):
        if self.settings.get("resize_window",True): self.u.resize(self.w,self.h)
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
            if self.settings.get("resize_window",True): self.u.resize(self.w,self.h)
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

    def cli(self, user_plist = None, sample_plist = None):
        # Let's normalize the plist paths - and use the latest sample.plist if no sample passed
        if not user_plist:
            print("User plist path is required!")
            exit(1)
        user_plist = self.u.check_path(user_plist)
        if not user_plist:
            print("User plist path invalid!")
            exit(1)
        # Try to load it
        try:
            with open(user_plist, "rb") as f:
                user_plist_data = plist.load(f)
        except Exception as e:
            print("User plist failed to load! {}".format(e))
            exit(1)
        # It loads - save it
        self.current_config = user_plist
        # Check the sample_plist as needed
        if sample_plist:
            sample_plist = self.u.check_path(sample_plist)
            if not sample_plist:
                print("Sample plist path invalid!")
                exit(1)
            # Try to load it
            try:
                with open(sample_plist, "rb") as f:
                    sample_plist_data = plist.load(f)
            except Exception as e:
                print("Sample plist failed to load! {}".format(e))
                exit(1)
            # Loads - we should be good - save it
            self.sample_config = sample_plist
        else:
            # Let's get the latest commit
            p = self.get_latest(use_release=False,wait=False,hide=True)
            if not p:
                print("Could not get the latest sample!")
                exit(1)
            self.sample_config,self.sample_plist = p
        self.compare(hide=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-u","--user-plist",help="Path to the local user plist.")
    parser.add_argument("-s","--sample-plist",help="Path to the sample plist - will get the latest commit from OC if none passed.")
    parser.add_argument("-w","--suppress-warnings",help="Suppress non-essential warnings when comparing.",action="store_true")
    parser.add_argument("-d","--dev-help",help="Show the help menu with developer options visible.",action="store_true")
    parser.add_argument("-p","--update-user",help=argparse.SUPPRESS,action="store_true")
    parser.add_argument("-l","--update-sample",help=argparse.SUPPRESS,action="store_true")
    parser.add_argument("-t","--no-timestamp",help=argparse.SUPPRESS,action="store_true")
    parser.add_argument("-b","--backup-original",help=argparse.SUPPRESS,action="store_true")
    args = parser.parse_args()

    if args.dev_help: # Update the developer options help, and show it
        update = {
            "update_user":"Pull changes into a timestamped copy (unless overridden by -t or -b) of the user plist.",
            "update_sample":"Pull changes into a timestamped copy (unless overridden by -t or -b) of the sample plist.",
            "no_timestamp":"Pull changes directly into the user or sample plist without a timestamped copy (requires -p or -l).",
            "backup_original":"Backup the user or sample plist with a timestamp before replacing it directly (requires -p or -l, overrides -t)"
        }
        for action in parser._actions:
            if not action.dest in update: continue
            action.help = update[action.dest]
        parser.print_help()
        exit()

    o = OCCC()
    if args.suppress_warnings: o.settings["suppress_warnings"] = True
    if args.update_user: o.settings["update_user"] = True
    if args.update_sample: o.settings["update_sample"] = True
    if args.no_timestamp: o.settings["no_timestamp"] = True
    if args.backup_original:
        o.settings["no_timestamp"] = False
        o.settings["backup_original"] = True
    if args.user_plist or args.sample_plist:
        # We got a required arg - start in cli mode
        o.cli(args.user_plist,args.sample_plist)
        exit()

    if 2/3 == 0:
        input = raw_input
    while True:
        try:
            o.main()
        except Exception as e:
            print("\nError: {}\n".format(e))
            input("Press [enter] to continue...")
