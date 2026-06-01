from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Project, Scan
from crawler.engine import CrawlerEngine
# This command is used to start crawling a website from terminal
# It creates project scan and runs crawler engine
class Command(BaseCommand):
 # This method is used to take input arguments from user
    def add_arguments(self, parser):
        parser.add_argument('domain', type=str)
        parser.add_argument('--max-pages', type=int, default=100)
 # Main function that runs command
    def handle(self, *args, **options):
        domain = options['domain']
        max_pages = options['max_pages']
 # Add http if missing in domain
        if not domain.startswith(('http://', 'https://')):
            domain = 'http://' + domain

        user, _ = User.objects.get_or_create(username='cli_user', defaults={'email': 'cli@example.com'})

        project, created = Project.objects.get_or_create(
            domain=domain,
            defaults={'user': user}
        )

        # Show message based on project creation
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created new Project for {domain}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Found existing Project for {domain}'))

        scan = Scan.objects.create(project=project, status='Pending')

        self.stdout.write(self.style.NOTICE(f'Starting scan {scan.id} for {domain}...'))
        
        try:
            engine = CrawlerEngine(scan_id=scan.id, max_pages=max_pages)
            engine.start()
            self.stdout.write(self.style.SUCCESS(f'Scan {scan.id} finished successfully.'))
        except Exception as e:
             # Handle error if scan fails
            self.stdout.write(self.style.ERROR(f'Scan {scan.id} failed: {e}'))
            scan.status = 'Failed'
            scan.save()
