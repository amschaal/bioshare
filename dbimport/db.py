from django.db import connection, connections



def dictfetchall(sql):
    cursor = connections['import_db'].cursor()
    cursor.execute(sql)
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()
    ]
    
