$(function() {
	var $camid;

	$.ajax({
		url: "/camera/getCameras",
		type: "POST",
		contentType: "application/json",
		success: function($response){
			$('#cams ul').empty();

			$index = 0;
			for(let $item of JSON.parse($response)){
				$('#cams ul').append('<li><button value="'+$index+'"'+($index==0?" class='active'":"")+'>'+$item.name+'</button></li>');
				$index++;
			}

			$('#cams button').on('click', function(){
				getPresets($(this));
			});

			// next step: load presets
			getPresets( $('#cams li:first-child button') );
			$('#move').show()
		},
		fail: function($response){ 
			configFail($btn,$response); 
		}
	});


	/*
	* handle cams
	*/
	function getPresets( $btn ){
		$camid = $btn.val();
		$toggleLabels = $('.toggleLabels').is(':checked');
		console.log($toggleLabels);

		$('#cams button').removeClass('active');
		
		$btn.addClass('active');
		
		$.ajax({
			url: "/camera/getPresets",
			type: "POST",
			contentType: "application/json",
			data: JSON.stringify({
				id: parseInt($camid),
			}),
			success: function($response){ 
				$('#presets ul').empty();

				for(let $item of JSON.parse($response).presets){
					$('#presets ul').append('<li'+($toggleLabels?'':' class="basic"')+'><button value="'+$item.token+'">'+$item.token+'</button><span class="label"> '+$item.label+'</span></li>');
				}

				// next step: load livestream
				//getLive();
				//showFooter();
			}
		});
	}

	/*
	 * getLive
	 * /
	function getLive(){
		// fail: 
		$('#move').hide()
	}

	/*
	 * resize video
	 * /
	var $w = $('#live img').width();
	var $h = ($w / 16 ) * 9;
	$('#live img').attr('height', $h ); // 9:16

	/*
	 * restore preset label setting from cookie
	 * /
	let $cookie_raw = document.cookie.split("; ");
	var $cookie = [];
	for( $c in $cookie_raw){
		let $line = $cookie_raw[$c].split("=");
		$cookie[$line[0]] = $line[1];
	}

	if( 'labels' in $cookie ){
		if( $cookie.labels == 'true' ){
			$('.toggleLabels').attr('checked',true);
			$('#presets ul li').removeClass('basic');
		}
	}

	/*
	 * toggle preset labels
	 */
	$('.toggleLabels').click(function(){
		if( $(this).is(':checked') ){
			$('#presets ul li').removeClass('basic');
			document.cookie = "labels=true;max-age=2628000"; //max-age = 1 month
		} else {
			$('#presets ul li').addClass('basic');
			document.cookie = "labels=false;max-age=2628000"; //max-age = 1 month
		}
	});

	/*
	 * handle preset
	 */
	$('#presets button').click(function( $e ){
		var $btn = $(this);

		$('#presets button').removeClass('active');
		$btn.addClass('active');
		
		$.ajax({
			url: "/camera/gotoPreset",
			type: "POST",
			contentType: "application/json",
			data: JSON.stringify({
				id: parseInt($camid),
				preset: parseInt($btn.val())
			}),
			fail: function($response){ 
				configFail($btn,$response); 
			}
		});
	});

	/*
	 * Websocket
	 */
	var $video = document.getElementById("preview"); // niet als jQuery object laden!
	if( $video !== null ){
		$video.addEventListener('contextmenu', function ($e) { 
			$e.preventDefault(); 
		});

		var $host = $video.getAttribute('data-host');
		if( $host != undefined ){
			var $stream = $video.getAttribute('data-stream');
			var $wfs = new Wfs();
			$wfs.attachMedia( $video, $host+$stream );
		} else {
			console.log( 'host undefined' );
		}
	}

	/*
	 * toggle voice
	 * /
	$('.toggleVoice').click(function(){
		if( $(this).is(':checked') ){
			$video.muted = false;
			$('#preview').removeAttr("muted");
		} else {
			$video.muted = true;
		}
	});

	/*
	 * set StreamPublish
	 * /
	$('#streampublish').click(function( $e ){
		var $btn = $(this);
		if( $btn.is(":checked") ){
			$val = 1;
		} else if( confirm("Live uitzending uitschakelen?") ) {
			$val = 0;
		} else {
			return false;
		}

		return $.post('/ptzcam/api/config', {task: 'publish', p: $val}).fail( function($response){ configFail($btn,$response); }, "json");
	});

	/*
	 * reboot
	 * /
	$('#reboot').click(function( $e ){
		if( confirm("Camera herstarten?") ) {
			var $btn = $(this);
			$.post('/ptzcam/api/config', {task: 'reboot'}).fail( function($response){ configFail($btn,$response); }, "json");
		}
	});
	
	/*
	 * move
	 * /
	var $moveID = null;
	var $touch = 'ontouchstart' in document.documentElement; // true | false
	$('#move button').on('click touchstart mousedown', function( $e ){ 
		$('#presets button').removeClass('active');

		var $clicks = $(".toggleClicks").is(":checked"); // true | false
		var $action = ($e.type == "click" && $clicks) ||
						($e.type == "touchstart" && $touch && !$clicks) ||
						($e.type == "mousedown" && !$touch && !$clicks);

		if( $action ){
			var $btn = $(this);
			var $id = $(this).attr("id");

//$('#debug').append("<p>btn: "+$id+"<br>type: "+$e.type+"<br>touch: "+$touch+"<br>clicks: "+$clicks+"<br>action: "+$action+"</p>");

			if( $id != 'stop' ){
				$moveID = $id;
				$.post('/ptzcam/api/config', {task: 'move', p: $id + "_start", s: 20}).fail( function($response){ configFail($btn,$response); }, "json");
			}
			if( $e.type == "click" ){
				$.post('/ptzcam/api/config', {task: 'move', p: $id + "_stop", s: 0}).fail( function($response){ configFail($btn,$response); }, "json");
			}
		}

//		console.log("touch: " + $touch + "\nclicks: " + $clicks + "\nevent: " + $e.type + "\naction: " + $action);
	});

	$('#move button').on('touchend mouseup', function( $e ){ 
		var $clicks = $(".toggleClicks").is(":checked"); // true | false
		var $action = ($e.type == "touchend" && $touch && !$clicks ) || 
						($e.type == "mouseup" && !$touch && !$clicks);
		
		if( $action ){
			var $btn = $(this);
			var $id = $(this).attr("id");
			if( $id != 'stop' ){
				$.post('/ptzcam/api/config', {task: 'move', p: $id + "_stop", s: 0}).fail( function($response){ configFail($btn,$response); }, "json");
			}
		}

//		console.log("touch: " + $touch + "\nclicks: " + $clicks + "\nevent: " + $e.type + "\naction: " + $action);
	});

	$('#move #stop').click( function(){ 
		if( $moveID != null ){
			var $btn = $(this);
			$.post('/ptzcam/api/config', {task: 'move', p: $moveID + "_stop", s: 0}).fail( function($response){ configFail($btn,$response); }, "json");
		}
	});
	
	/*
	 * configFail
	 */
	function configFail($btn, $response){
		console.log($response.responseJSON);
		$('#debug').append("<p>"+$response.responseJSON.message+"</p>");
		
		if( $response.responseJSON.error ){
			$btn.css("background-color", "red");
			if( $response.responseJSON.message == "Unauthorized" ){
				location.reload(true);
			}
		}
	}
});