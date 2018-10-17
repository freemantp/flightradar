from playhouse.migrate import *
from playhouse.reflection import *

from adsb.config import Config

conf = Config()
conf.from_file('config.json')

my_db =  SqliteDatabase('{:s}/positions.db'.format(conf.data_folder))
migrator = SqliteMigrator(my_db)
introspector = Introspector.from_database(my_db)

analysis = introspector.introspect()

before = analysis.columns['position']['alt'].nullable

archive_field = BooleanField(default=False)

print("Starting DB schema migration... ")

migrate(
    migrator.drop_not_null('position', 'alt'),
    migrator.add_column('position', 'archived', archive_field),
)

analysis = introspector.introspect()
after = analysis.columns['position']['alt'].nullable
archive = 'archived' in analysis.columns['position']

if not before and after and archive:
    print("-> Successful")
else:
    print("-> Not successful")

