"""
Management command to generate OpenAPI schema from Django views using drf-spectacular.
This ensures the openapi.yaml file is always in sync with the actual API.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
from drf_spectacular.generators import SchemaGenerator
import yaml


class Command(BaseCommand):
    help = 'Generate OpenAPI 3.0 schema from Django REST Framework views and save to openapi.yaml'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='openapi.yaml',
            help='Output file path (default: openapi.yaml)',
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['yaml', 'json'],
            default='yaml',
            help='Output format (default: yaml)',
        )

    def handle(self, *args, **options):
        output_file = options['file']
        output_format = options['format']
        
        self.stdout.write('Generating OpenAPI schema from Django views...')
        
        try:
            # Create schema generator
            # drf-spectacular will automatically discover all URL patterns
            generator = SchemaGenerator()
            
            # Generate schema
            schema = generator.get_schema(request=None, public=True)
            
            # drf-spectacular returns an OpenAPISchema object with .data attribute
            # Convert to dict
            if hasattr(schema, 'data'):
                schema_dict = dict(schema.data)
            else:
                # Fallback: try to serialize directly
                import json
                schema_json = json.dumps(schema, default=str)
                schema_dict = json.loads(schema_json)
            
            # Write to file
            base_dir = Path(settings.BASE_DIR)
            output_path = base_dir / output_file
            
            if output_format == 'yaml':
                with open(output_path, 'w', encoding='utf-8') as f:
                    yaml.dump(schema_dict, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
                self.stdout.write(
                    self.style.SUCCESS(f'✅ OpenAPI schema generated successfully: {output_path}')
                )
            else:
                import json
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(schema_dict, f, indent=2, ensure_ascii=False)
                self.stdout.write(
                    self.style.SUCCESS(f'✅ OpenAPI schema generated successfully: {output_path}')
                )
            
            # Print summary
            paths_count = len(schema_dict.get('paths', {}))
            components_count = len(schema_dict.get('components', {}).get('schemas', {}))
            
            self.stdout.write(f'\n📊 Schema Summary:')
            self.stdout.write(f'   - Endpoints: {paths_count}')
            self.stdout.write(f'   - Schemas: {components_count}')
            self.stdout.write(f'\n💡 Next steps:')
            self.stdout.write(f'   1. Review the generated schema: {output_path}')
            self.stdout.write(f'   2. Regenerate TypeScript clients:')
            self.stdout.write(f'      cd frontend_inventory_and_orders/ts-clients')
            self.stdout.write(f'      npm run generate:all')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error generating schema: {str(e)}')
            )
            import traceback
            self.stdout.write(traceback.format_exc())
            raise



