import logging
import time
import urllib2
from operator import itemgetter

logging.basicConfig(filename='diagnose.log', filemode='w',
                    level=logging.DEBUG)

# helper function
def extract_domains_from_url(url):
    """
    Extrait un domaine d'une URL

    Retourne le tuple T qui contient
    T[0]: domaine avec le bon protocol (http://domain or https://domain)
    T[1]: domaine sans le protocol (sans http:// or https://)
    """
    protocol_http = 'http://' 
    protocol_https = 'https://' 
    protocol = ''
    if url.startswith(protocol_http):
        url = url.replace(protocol_http, '')
        protocol = protocol_http
    elif url.startswith(protocol_https):
        url = url.replace(protocol_https, '')
        protocol = protocol_https
    else:
        logging.debug("Erreur lors de l'extraction du domaine: " + url)
        return ''
    domain = url[:url.find('/')]
    return (protocol + domain, domain)


class HTMLPage(object):
    """
    represente une page HTML. Le constructeur prend comme argument une
    URL et constuit un objet HTMLPage

    L'objet a 3 attributs:
        -url: l'URL qui correspond a la page Web
        -_html_it: un iterateur qui parcours le code HTML, une ligne 
                   a la fois
        -urls: la liste de toutes les URLs contenues dans la page
        -http_code: le code retourne par le protocol HTTP lors de 
                    l'acces a la page
                    *http_code=0 signifie une erreur dans l'URL, 
                    *http_code < 0 signifie une exception en accedant 
                    a l'URL

    """

    def __init__(self, url):
        self.http_code = 0
        self.url = url
        self._html_it = self.page_fetcher(self.url)
        self.urls = self.extract_urls_from_page()
        logging.debug('+'*80 + '\npage {}\n'.format(self.url))
        logging.debug('extracted URLs {}\n'.format(self.urls) + '+'*80 + '\n')

    def page_fetcher(self, url):
        """
        accede a l'URL et retourne un objet qui permet de parcourir 
        le code HTML (voir la documentation de urllib2.urlopen)
        """
        
        # surcharge la classe Request pour faire des requetes HEAD qui
        # pemettent de collecter que l'entete de la page. C'est utile
        # lorsque la page ne contient pas de code HTML et donc pas
        # d'URL.  On peut ainsi obtenir un code HTTP sans avoir besoin
        # de telecharger toute la page.
        class HeadRequest(urllib2.Request):
            def get_method(self):
                return "HEAD"
        
        def is_html_page(url):
            """
            simple heuristique pour tester si une page est ecrite en
            HTML. Il y a des cas mal identifies par cette heuristique,
            mais elle est suffisante pour nos besoins. Par exemple:
            http://inria.fr sera identifie comme non html de meme que
            toutes les pages qui utilisent des points dans le nom d'un
            repertoire.
            """
            #if there is no extension, it is a directory, so it
            #defaults to an index.html page
            if url.endswith('/'):
                return True
            else:
                url_tokens = url.split('/')
                #if there is no extension, it is a directory, so it
                #defaults to an index.html page
                if '.' not in url_tokens[-1]:
                    return True
                elif ('html' in url_tokens[-1].lower() or   
                      'htm' in url_tokens[-1].lower()):
                    return True
                else:
                    return False
                
        try:
            if is_html_page(url):
                page = urllib2.urlopen(url)
            else:
                logging.debug('HEAD request for {}'.format(url))
                page = urllib2.urlopen(HeadRequest(url))
            self.http_code = page.getcode()
            return page
        except urllib2.HTTPError as e:
            logging.warning('HTTPError: cannot open {}. Reason {}, code {}'
                            .format(url, e.reason, e.code))
            self.http_code = e.code
            return []

        except urllib2.URLError as e:
            logging.warning('URLError: cannot open {}. Reason {}'
                            .format(url, e.reason))
            self.http_code = -1
            return []
        except Exception as e:
            logging.error('uncatched error {}\nfor URL {}'.format(e, url))
            self.http_code = -2
            return []

    def extract_urls_from_page(self):
        """
        Construit la liste de toutes les URLs contenu dans le corps de
        la page HTML

        On identifie une URL parce qu'elle est precedee de href=. Le
        parsing que l'on implement est imparfait, mais un vrai parsing
        intelligent demanderait une analyse syntaxique trop complexe
        pour nos besoins.
        """

        # parse the page to extract all URLs in href field and in the
        # body of the document
        list_urls = []
        is_body = False
        for line in self._html_it:
            # line = line.lower()
            if is_body:
                if "href=" in line.lower():
                    # extract everything between href=" and "> probably
                    # not bullet proof, but should work most of the
                    # time. 
                    url_separator = line[line.lower().find('href=') + 5]
                    line = line[line.lower().find('href=') + 6:]
                    line = line[:line.lower().find(url_separator)]

                    list_urls.append(line)
                elif "http://" in line or "https://" in line:
                    logging.debug('this URL was not extracted: ' + line)
            else:
                # do not end with > in order to deal with arguments
                # without complexe parsing
                if '<body' in line:
                    is_body = True

                    
        logging.debug('in extract_urls_from_page\n' + '-'*80 + '\n')
        logging.debug('All extracted URLs:\n')
        logging.debug('{}\n'.format(list_urls))
        # keep only http and https
        filtered_list_urls = [x for x in list_urls
                              if x.lower().startswith('http')
                              or x.lower().startswith('https')]

        logging.debug('filtered URLs (http, https):\n')
        logging.debug('{}\n'.format(filtered_list_urls))
        # and reconstruct relative links ./
        filtered_list_urls.extend([self.url[:self.url.rfind('/')] + x[1:]
                                   for x in list_urls
                                   if x.startswith('./')])
        logging.debug('filtered URLs (relatives ./):\n')
        logging.debug('{}\n'.format(filtered_list_urls))

        # and reconstruct relative links /
        filtered_list_urls.extend([extract_domains_from_url(self.url)[0] 
                                   + x for x in list_urls
                                   if x.startswith('/')]) 

        logging.debug('filtered URLs (relatives /):\n')
        logging.debug('{}\n'.format(filtered_list_urls))

        # debug
        # print [x for x in list_urls if x.startswith('./')]

        return list(set(filtered_list_urls))


class Crawler(object):
    """
    Cette classe permet de creer l'objet qui va gerer le crawl. Cette
    objet est iterable et l'iterateur va, a chaque tour, retourner un
    nouvel objet HTMLPage.

    Le constructeur prend comme arguments
    -seed_url: l'URL de la page a partir de laquelle on demarre le crawl
    -max_crawled_sites: le nombre maximum de sites que l'on va crawler
     (10**100 par defaut)
    -domain_filter: la liste des domaines sur lesquels le crawler 
    doit rester (pas de filtre par defaut)
    """

    def __init__(self, seed_url, max_crawled_sites=10 ** 100,
                 domain_filter=None):
        """
        Constructeur du crawler

        -seed_url: l'URL de la page a partir de laquelle on demarre le crawl
        -max_crawled_sites: le nombre maximum de sites que l'on va crawler
        (10**100 par defaut)
        -domain_filter: la liste des domaines sur lesquels le crawler 
        doit rester (pas de filtre par defaut)
        """
        if domain_filter is None:
            domain_filter = []
        self.domain_filter = domain_filter
        self.seed_url = seed_url
        self.max_crawled_sites = max_crawled_sites

        # Each key is a URL, and the value for the key url is the list
        # of sites that referenced this url. This dict is used to find
        # sites that references given URLs in order to diagnose
        # buggy Web pages.
        self.sites_to_be_crawled_dict = {}

        # set of the sites still to be crawled
        self.sites_to_be_crawled = set([])

        # set of the sites/domains already crawled
        self.sites_crawled = set([])
        self.domains_crawled = set([])
        
        # duration of the last crawl
        self.last_crawl_duration = 0

    def update_sites_to_be_crawled(self, page):
        """
        Prend un objet HTMLpage comme argument et trouve toutes les
        URLs presente dans la page HTML correspondante. Cette methode
        met a jour le dictionnaire sites_to_be_crawled_dict et
        l'ensemble sites_to_be_crawled. On ne met pas a jour le
        dictionnaire et le set si l'URL correspondant a l'objet
        HTMLpage n'est pas dans la liste de domaines acceptes.
        """
        # check the domain of the page from which we got URLs
        pass_filter = False
        #extracted_domain =  extract_domains_from_url(page.url)[1]
        for domain in self.domain_filter:
            if domain in page.url: #extracted_domain:
                pass_filter = True

        logging.debug('*'*80 + '\n')
        logging.debug('site crawled providing the URLs : {}\n'.format(page.url))
        logging.debug('pass filter state: {}\n'.format(pass_filter))
        if pass_filter:
            logging.debug('passes the filter \n')
            logging.debug('list of urls to be added: {}'.format(page.urls))
            # update the list of sites to be crawled with the URLs
            for url in page.urls:
                # update the dict even if url already crawled (to get
                # comprehensif information)
                if url in self.sites_to_be_crawled_dict:
                    self.sites_to_be_crawled_dict[url].append(page.url)
                else:
                    self.sites_to_be_crawled_dict[url] = [page.url]

                # update the set if url not already crawled
                if url not in self.sites_crawled:
                    self.sites_to_be_crawled.add(url)


    def __repr__(self):
        """
        permet d'afficher simplement des informations sur l'etat
        courant du crawl.

        retourne une chaine de caracteres donnant:
        -le nombre sites et domaines deja crawle
        -le nombre de site encore a crawler
        -la duree du dernier crawl
        """
        output = ('#' * 60 + '\nInitial URL: {}'.format(self.seed_url)
                   + '\nSites/domains already crawled {}/{}'.format(
                 len(self.sites_crawled),
                 len(self.domains_crawled))
                   + '\nSites to be crawled {}'.format(
                 len(self.sites_to_be_crawled))
                   + '\n crawl duration {}'.format(
                 self.last_crawl_duration)
                  )
        return output

    def __iter__(self):
        """
        Cette methode est implemente comme une fonction generatrice. A
        chaque appel de next() sur l'iterateur, on obtient un nouvel
        objet HTMLPage qui correspond a une URL qui etait dans
        l'ensemble des URLs a crawler. 

        On ne donne aucune garantie sur l'ordre de parcours des URLs
        """

        # case of the first page
        start_time = time.time()
        page = HTMLPage(self.seed_url)
        self.last_crawl_duration = time.time() - start_time
        self.sites_crawled.add(seed_url)
        self.domains_crawled.add(extract_domains_from_url(seed_url)[1])
        self.update_sites_to_be_crawled(page)
        yield page 
        
        # all the other pages
        while (self.sites_to_be_crawled and
                       len(self.sites_crawled) < self.max_crawled_sites):
            url = self.sites_to_be_crawled.pop()
            start_time = time.time()
            page = HTMLPage(url)
            self.last_crawl_duration = time.time() - start_time
            self.sites_crawled.add(url)
            self.domains_crawled.add(extract_domains_from_url(url)[1])
            self.update_sites_to_be_crawled(page)
            yield page
        raise StopIteration


# Let's answer funny questions in a few lines of code

####################################################
# 1) what are the dead URLs 
def get_dead_pages(url, domain):
    crawl = Crawler(url, domain_filter=domain)
    dead_urls = []
    for page in crawl:
        # just to see progress on the terminal
        print crawl
        print page.http_code, page.url

        if page.http_code != 200:
            dead_urls.append((page.http_code, page.url))        

    with open('dead_pages.txt', 'w') as dump_file:
        dump_file.write('number of dead URLs (non 202) : {}\n'
                        .format(len(dead_urls)))
        dump_file.write('-'*80 + '\n')
        for url in dead_urls:
            dump_file.write('Dead URL ({}): {}\n'.format(url[0],url[1]))
            dump_file.write('Sites referencing this URL:\n')
            for site in crawl.sites_to_be_crawled_dict[url[1]]:
                dump_file.write('     {}\n'.format(site))
            dump_file.write('\n')

# 2) what are the less responsive sites
def get_slow_pages(url, domain):
    crawl = Crawler(url, domain_filter=domain)
    pages_responsivness = []
    for page in crawl:
        # just to see progress on the terminal
        print crawl
        print page.http_code, page.url
        pages_responsivness.append((crawl.last_crawl_duration, page.url))

    pages_responsivness.sort(key=itemgetter(0), reverse=True)

    with open('slow_pages.txt', 'w') as dump_file:
        dump_file.write('Pages ordered from the slowest to the fastest\n')
        dump_file.write('-'*80 + '\n')
        for line in pages_responsivness:
            dump_file.write('{:.2f} seconds: {}\n'.format(line[0], line[1]))

if __name__ == '__main__':
    seed_url = 'http://www-sop.inria.fr/members/Arnaud.Legout/'
    domain = ['www-sop.inria.fr/members/Arnaud.Legout']
    get_dead_pages(s, domain)
    get_slow_pages(s, domain)

    logging.shutdown()
