from bs4 import BeautifulSoup
from urllib.parse import urlparse
# This class is used to analyze a web page for accessibility issues
# It checks HTML content and finds WCAG problems
class PageAnalyzer:
    def __init__(self, html_content, url):
        self.html_content = html_content
        self.url = url
         # Convert HTML into parseable structure
        self.soup = BeautifulSoup(html_content, 'html.parser')
        self.issues = []
# This method runs all accessibility checks
    def run_checks(self):
        self.check_missing_alt()
        self.check_missing_form_labels()
        self.check_heading_hierarchy()
        self.check_missing_lang()
        self.check_broken_links()
        return self.issues
# This method adds an issue to the list
    def add_issue(self, wcag_id, message, element_html, fix_suggestion, severity='medium'):
        self.issues.append({
            'wcag_id': wcag_id,
            'message': message,
            'element_html': str(element_html)[:500],  # Limit size
            'fix_suggestion': fix_suggestion,
            'severity': severity
        })
# Check if images have alt text
    def check_missing_alt(self):
        images = self.soup.find_all('img')
        for img in images:
            alt = img.get('alt')
            if alt is None or str(alt).strip() == "":
                self.add_issue(
                    wcag_id='1.1.1',
                    message='Image is missing alt text or alt text is empty.',
                    element_html=img,
                    fix_suggestion='Add a descriptive alt attribute to the image.',
                    severity='high'
                )

    def check_missing_form_labels(self):
        inputs = self.soup.find_all(['input', 'textarea', 'select'])
        for inp in inputs:
            input_type = inp.get('type')
            if input_type in ['hidden', 'submit', 'button', 'image', 'reset']:
                continue

            # Check if it has an id and is referenced by a label
            inp_id = inp.get('id')
            has_label = False
            if inp_id:
                label = self.soup.find('label', attrs={'for': inp_id})
                if label:
                    has_label = True

            # Check for aria-label or aria-labelledby
            has_aria = inp.get('aria-label') or inp.get('aria-labelledby')

            if not has_label and not has_aria:
                self.add_issue(
                    wcag_id='3.3.2',
                    message='Form input is missing an associated label.',
                    element_html=inp,
                    fix_suggestion='Provide a <label> with a "for" attribute matching the input\'s "id", or use "aria-label".',
                    severity='high'
                )

    def check_heading_hierarchy(self):
        headings = self.soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        current_level = 0
        for h in headings:
            level = int(h.name[1])
            if current_level != 0 and level > current_level + 1:
                self.add_issue(
                    wcag_id='1.3.1',
                    message=f'Heading level skipped from h{current_level} to h{level}.',
                    element_html=h,
                    fix_suggestion='Ensure headings are used in sequential order without skipping levels.',
                    severity='medium'
                )
            current_level = level

    def check_missing_lang(self):
        html_tag = self.soup.find('html')
        if html_tag:
            lang = html_tag.get('lang')
            if not lang or str(lang).strip() == "":
                self.add_issue(
                    wcag_id='3.1.1',
                    message='The <html> element is missing a "lang" attribute.',
                    element_html=html_tag,
                    fix_suggestion='Add a lang attribute to the <html> tag (e.g., lang="en").',
                    severity='critical'
                )
        else:
            self.add_issue(
                wcag_id='3.1.1',
                message='Page is missing the <html> element entirely.',
                element_html='<Missing HTML tag>',
                fix_suggestion='Ensure the document structure starts with an <html> tag.',
                severity='critical'
            )

    def check_broken_links(self):
        links = self.soup.find_all('a')
        for a in links:
            href = a.get('href')
            if href is None or str(href).strip() == "" or str(href).strip() == "#":
                self.add_issue(
                    wcag_id='2.4.4',
                    message='Link contains an empty or # href attribute, suggesting it may be broken or unnavigable.',
                    element_html=a,
                    fix_suggestion='Provide a valid URL in the href attribute.',
                    severity='medium'
                )
