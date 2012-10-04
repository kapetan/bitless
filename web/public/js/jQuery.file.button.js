jQuery.fn.file = function(fn) {
	return this.each(function() {
		var el = $(this);
		var holder = $('<div></div>').appendTo(el).css({
			position:'absolute',
			width:el.width()+'px',
			height:el.height()+'px',
			overflow:'hidden',
			opacity:0
		});	

		var wid = 0;
		var inp;

		var addInput = function() {
			var current = inp = holder.html('<input '+(window.FormData ? 'multiple ' : '')+'type="file" style="position:absolute">').find('input');					

			wid = wid || current.width();

			current.change(function() {
				current.unbind('change');

				addInput();
				fn(current[0]);
			});
		};
		var position = function(e) {
			holder.offset(el.offset());					

			if (e) {
				inp.offset({left:e.pageX-wid+25, top:e.pageY-10});						
			}
		};

		addInput();

		el.mouseover(position);
		el.mousemove(position);
		position();		
	});
};