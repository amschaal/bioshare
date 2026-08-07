# Merge migration joining the two 0032 branch leaves: the email-footer
# schema (custom-email-footers branch) and the real_path/ShareLog indexes
# (worker-exhaustion-hardening branch). No operations; it only unifies the
# migration graph.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bioshareX', '0032_emailfooter_share_email_footer'),
        ('bioshareX', '0032_share_real_path_index_sharelog_index'),
    ]

    operations = []
