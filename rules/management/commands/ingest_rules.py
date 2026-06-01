import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from rules.models import Rule
# This command is used to load WCAG rules from json file into database
class Command(BaseCommand):
# Main function that runs when command is executed
    def handle(self, *args, **options):
        file_path = os.path.join(settings.BASE_DIR, 'rules', 'wcag_rules.json')
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File not found: {file_path}'))
            return
 # Open and read json file
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                rules_data = json.load(f)
            except json.JSONDecodeError:
                self.stdout.write(self.style.ERROR('Invalid JSON format in wcag_rules.json'))
                return

        created_count = 0
        updated_count = 0
# Create new rule or update existing one
        for rule_data in rules_data:
            required_fields = ['wcag_id', 'title', 'level', 'category', 'check_type']
            if not all(field in rule_data for field in required_fields):
                self.stdout.write(self.style.WARNING(f'Skipping invalid rule data: {rule_data}'))
                continue

            rule, created = Rule.objects.update_or_create(
                wcag_id=rule_data['wcag_id'],
                defaults={
                    'title': rule_data['title'],
                    'level': rule_data['level'],
                    'category': rule_data['category'],
                    'check_type': rule_data['check_type'],
                    'version': ",".join(rule_data['version']) if isinstance(rule_data.get('version'), list) else rule_data.get('version', '2.0,2.1,2.2'),
                    'logic': rule_data.get('logic', ''),
                    'fix_suggestion': rule_data.get('fix_suggestion', ''),
                }
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully ingested rules. Created: {created_count}, Updated: {updated_count}'))
