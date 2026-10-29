from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0004_documentline_source_service_entry_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="documentline",
            name="quantity",
            field=models.DecimalField(decimal_places=6, max_digits=15),
        ),
    ]
