jQuery.extend( jQuery.fn.dataTableExt.oSort, {
    "file-size-pre": function ( a ) {
        var x = a.substring(0,a.length - 2);
        var x_unit = 1;
        switch(a.substring(a.length - 2, a.length)){
        	case 'KB':
        		x_unit = 1024;
        		break;
        	case 'MB':
        		x_unit = 1048576;
        		break;
        	case 'GB':
        		x_unit = 1073741824;
        		break;
        }
//        var x_unit = (a.substring(a.length - 2, a.length) == "KB" ?
//            1024 : (a.substring(a.length - 2, a.length) == "MB" ?
//            1048576 : (a.substring(a.length - 2, a.length) == "GB" ? 1073741824 : 1));
          
        return parseInt( x * x_unit, 10 );
    },
 
    "file-size-asc": function ( a, b ) {
        return ((a < b) ? -1 : ((a > b) ? 1 : 0));
    },
 
    "file-size-desc": function ( a, b ) {
        return ((a < b) ? 1 : ((a > b) ? -1 : 0));
    }
} );