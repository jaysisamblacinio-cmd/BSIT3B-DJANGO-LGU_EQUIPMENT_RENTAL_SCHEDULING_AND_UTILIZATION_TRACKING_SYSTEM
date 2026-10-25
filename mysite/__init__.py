import django.db.backends.mysql.features

# Patch for MariaDB 10.4 compatibility (disables RETURNING clause on INSERT which was added in 10.5)
django.db.backends.mysql.features.DatabaseFeatures.minimum_database_version = (10, 4)
django.db.backends.mysql.features.DatabaseFeatures.can_return_columns_from_insert = False
