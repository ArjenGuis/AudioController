// Send Tornado's XSRF token on every ajax POST (double-submit cookie) (S5).
$.ajaxSetup({
	beforeSend: function(xhr) {
		var m = document.cookie.match(/(?:^|;\s*)_xsrf=([^;]+)/);
		if (m) { xhr.setRequestHeader("X-Xsrftoken", decodeURIComponent(m[1])); }
	}
});


$(function() {
	var $camid = null;
	var $cameras = null;
	var $wfs = new Wfs();
	var $presetTimeout;
	var $publishTimeout;

	// getPresets, getLive en getStreamPublish schrijven alle drie naar dezelfde .alert
	// en lopen parallel; voorheen won simpelweg wie het laatst terugkwam (een werkende
	// video verborg zo "Geen live uitzending", en de 60s-poll zette hem later weer terug).
	// Houd de uitslagen daarom hier bij en render de melding centraal, in vaste volgorde
	// van ernst. null = nog onbekend.
	var $camAvailable = null;
	var $videoAvailable = null;
	var $streamPublish = null;
	// volgnummer per camerakeuze, zodat een laat antwoord van de vorige camera
	// de melding (of de videostream) van de huidige niet overschrijft
	var $liveSeq = 0;

	function renderLiveAlert(){
		if( $camAvailable === false ){
			$('#live .alert').text("Camera is niet beschikbaar.").show();
		} else if( $videoAvailable === false ){
			$('#live .alert').text("Video is niet beschikbaar.").show();
		} else if( $streamPublish === false ){
			$('#live .alert').text("Geen live uitzending").show();
		} else {
			$('#live .alert').hide();
		}
	}

	getLogin();

	/*
	* get login
	*/
	function getLogin(){
		$('#login, #cams, #presets, #live, #live video, #move, #footer, #user').hide();

		$.ajax({
			url: "/login/login",
			type: "POST",
			contentType: "application/json",
			dataType: 'json',
			success: function($response){
				if( $response.success ){
					showLoggedIn( $response.username );
				} else {
					$('#login').show();

					$('#login button').click( function(){
						$.ajax({
							url: "/login/login",
							type: "POST",
							contentType: "application/json",
							dataType: 'json',
							data: JSON.stringify({
								username: $('#login #current-username').val(),
								password: $('#login #current-password').val()
							}),
							success: function($response){
								if( $response.success ){
									showLoggedIn( $response.username );
								} else {
									$('#login .fout').show();
								}
							}
						});
					});
				}
			}
		});
	}

	// Beide login-paden (al ingelogd via cookie, en net ingelogd via het formulier)
	// moeten exact dezelfde elementen tonen. Ze stonden apart uitgeschreven en waren
	// uit elkaar gelopen: het formulier-pad toonde #live niet, dus na een verse login
	// bleef de videocontainer verborgen tot een refresh (alleen zichtbaar als de
	// camera onbereikbaar was, want die foutmelding doet zelf $('#live').show()).
	// De naam komt van de server, niet uit het invoerveld: login is niet
	// hoofdlettergevoelig, dus "Arjen" hoort als "arjen" in de UI en in het
	// wijzigformulier te staan (anders hernoemt setUser het account).
	function showLoggedIn(username){
		$('#login').hide();
		$('#cams, #live, #user').show();

		setUsername( username || $('#login #current-username').val() );

		getCameras();
	}

	function setUsername(username){
		$('#user .username').text(username)
		$('#user #current-username').val(username)
	}

	/*
	* get cams
	*/
	function getCameras(){
		$('#login, #presets, #live video, #move, #footer').hide();

		$.ajax({
			url: "/camera/getCameras",
			type: "POST",
			contentType: "application/json",
			dataType: 'json',
			success: function($response){
				if( $response.success ){
					$('#cams').show();
					$('#cams ul').empty();
					$cameras = $response.cameras;

					$index = 0;
					for(let $item of $cameras){
						var $button = $('<button>').attr('value', $index).text($item.name);
						if( $index == 0 ){
							$button.addClass('active');
						}
						$('#cams ul').append( $('<li>').append($button) );
						$index++;
					}

					$('#cams button').on('click', function(){
						getPresets($(this));
					});

					// next step: load presets
					getPresets( $('#cams li:first-child button') );
				} else {
					$('#live .alert').text($response.error).show();  // niet ingelogd
				}
			}
		});
	}

	/*
	* handle cams
	*/
	function getPresets( $btn ){
		$('#login, #presets, #live video, #move, #footer').hide();
		clearTimeout($presetTimeout);
		clearTimeout($publishTimeout);

		$camid = $btn.val();
		$toggleLabels = $('.toggleLabels').is(':checked');

		$('#cams button').removeClass('active');
		$btn.addClass('active');

		// nieuwe camerakeuze: uitslagen van de vorige gelden niet meer
		var $seq = ++$liveSeq;
		$camAvailable = null;
		$videoAvailable = null;
		$streamPublish = null;
		renderLiveAlert();

		// De streampublish-status komt van /ajaxcom en heeft de trage ONVIF-handshake
		// van getPresets niet nodig. Meteen starten in plaats van in de success-callback,
		// anders verschijnt "Geen live uitzending" op een Pi pas seconden later.
		getStreamPublish();

		// restart wfs
		$wfs.destroy();
		$wfs = null;
		$wfs = new Wfs();

		$.ajax({
			url: "/camera/getPresets",
			type: "POST",
			contentType: "application/json",
			dataType: 'json',
			data: JSON.stringify({
				id: parseInt($camid),
			}),
			success: function($response){
				if( $seq !== $liveSeq ){
					return;
				}
				if( $response.err == 'connection' ){
					$('#live').show();
					$camAvailable = false;
					renderLiveAlert();
				} else {
					$camAvailable = true;
					renderLiveAlert();

					// clear preset buttons
					$('#presets ul').empty();

					// add preset buttons to dom
					for(let $item of $response.presets){
						var $li = $('<li>');
						if( !$toggleLabels ){
							$li.addClass('basic');
						}
						var $button = $('<button>').attr('value', $item.token).addClass('preset_' + $item.token).text($item.token);
						var $span = $('<span>').addClass('label').text(' ' + $item.label);
						$li.append($button).append($span);
						$('#presets ul').append($li);
					}
					$('#move, #presets, #footer').show();
					
					checkActivePreset();

					// add preset click event
					$('#presets button').click(function( $e ){
						gotoPreset( $(this) );
					});

					// load livestream
					getLive();

					// set Instellingen link
					$('#footer .caminstellingen').attr('href','http://'+$cameras[$camid].url_extern+':'+$cameras[$camid].port_http)
				}
			}
		});
	}

	function checkActivePreset(){
		$.ajax({
			url: "/camera/getActivePreset",
			type: "POST",
			contentType: "application/json",
			dataType: 'json',
			data: JSON.stringify({
				id: parseInt($camid),
			}),
			success: function($response){ 
				$('#presets ul button').removeClass('active');
				$('#presets ul button.preset_'+$response).addClass('active')

				$presetTimeout = setTimeout(checkActivePreset, 2000);
			}
		});
	}

	/*
	 * getLive
	 */
	function getLive(){
		var $seq = $liveSeq;

		$('#live video').hide();

		$.ajax({
			url: "/camera/getLive",
			type: "POST",
			contentType: "application/json",
			dataType: 'json',
			data: JSON.stringify({
				id: parseInt($camid),
			}),
			success: function($response){
				if( $seq !== $liveSeq ){
					// antwoord van een inmiddels verlaten camera: niet de stream van
					// de vorige camera aan de speler hangen
					return;
				}
				if( $response.success ){
					if( $response.uri !== false ){
						var $video = document.getElementById("preview"); // niet als jQuery object laden!
						if( $video !== null ){
							$video.addEventListener('contextmenu', function ($e) {
								$e.preventDefault();
							});

							$wfs.attachMedia( $video, "ws://"+$cameras[$camid].url_extern+":"+$cameras[$camid].port_ws+$response.uri );
						}
						$('#live video').show();
						$videoAvailable = true;
					} else {
						//$('#live .alert').text($response.error).show();
						$videoAvailable = false;
					}
				} else {
					//console.error('getLive fail: '+$response.error);
					$videoAvailable = false;
				}
				renderLiveAlert();
			}
		});
	}

	/*
	 * restore preset label setting from cookie
	 */
	let $cookie_raw = document.cookie.split("; ");
	var $cookie = [];
	for( $c in $cookie_raw){
		let $line = $cookie_raw[$c].split("=");
		$cookie[$line[0]] = $line[1];
	}

	if( 'camera_app_labels' in $cookie ){
		if( $cookie.camera_app_labels == 'true' ){
			$('.toggleLabels').attr('checked',true);
			$('#presets ul li').removeClass('basic');
		}
	}
	if( 'camera_app_audio' in $cookie ){
		$('.toggleAudio').attr('checked', ($cookie.camera_app_audio == 'true') );
		toggleAudio();
	}

	/*
	 * toggle preset labels
	 */
	$('.toggleLabels').click(function(){
		if( $(this).is(':checked') ){
			$('#presets ul li').removeClass('basic');
			document.cookie = "camera_app_labels=true;max-age=2628000"; //max-age = 1 month
		} else {
			$('#presets ul li').addClass('basic');
			document.cookie = "camera_app_labels=false;max-age=2628000"; //max-age = 1 month
		}
	});

	/*
	 * handle preset
	 */
	function gotoPreset( $btn ){
		$('#presets button').removeClass('active');
		$btn.addClass('active');
		
		$.ajax({
			url: "/camera/gotoPreset",
			type: "POST",
			contentType: "application/json",
			data: JSON.stringify({
				id: parseInt($camid),
				preset: parseInt($btn.val())
			})
		});
	}

	/*
	 * StreamPublish
	 */
	function getStreamPublish(){
		var $seq = $liveSeq;

		$.ajax({
			url: "/camera/getStreamPublish",
			type: "POST",
			contentType: "application/json",
			dataType: 'json',
			data: JSON.stringify({
				id: parseInt($camid),
			}),
			success: function($response){
				if( $seq !== $liveSeq ){
					// antwoord van een inmiddels verlaten camera
					return;
				}

				$('#footer .streampublish input').prop('checked', $response.success)

				// !! zodat elke falsy waarde "geen uitzending" betekent, zoals voorheen;
				// null blijft gereserveerd voor "nog onbekend"
				$streamPublish = !!$response.success;
				renderLiveAlert();

				$publishTimeout = setTimeout(getStreamPublish, 60000);
			}
		});
	}
	$('#footer .streampublish input').click(function( $e ){
		var $btn = $(this);
		if( $btn.is(":checked") ){
			$val = 1;
		} else if( confirm("Live uitzending uitschakelen?") ) {
			$val = 0;
		} else {
			return false;
		}

		$.ajax({
			url: "/camera/setStreamPublish",
			type: "POST",
			contentType: "application/json",
			dataType: 'json',
			data: JSON.stringify({
				id: parseInt($camid),
				publish: $val,
			}),
			success: function(){
				$streamPublish = !!$val;
				renderLiveAlert();
			}
		});
	});

	/*
	 * toggleAudio
	 */
	$('.toggleAudio').click(function(){
		toggleAudio();
	});

	function toggleAudio(){
		$video = document.getElementById("preview");
		if( $('.toggleAudio').is(':checked') ){
			$video.muted = false;
			$('#preview').removeAttr("muted");
			document.cookie = "camera_app_audio=true;max-age=2628000"; //max-age = 1 month
		} else {
			$video.muted = true;
			$('#preview').attr("muted", "");
			document.cookie = "camera_app_audio=false;max-age=2628000"; //max-age = 1 month
		}
	}

	/*
	 * reboot
	 */
	$('#camreboot').click(function( $e ){
		if( confirm("Camera herstarten?") ) {
			clearTimeout($presetTimeout);
			setTimeout(checkActivePreset, 45000);

			var $btn = $(this);
			$.ajax({
				url: "/camera/reboot",
				type: "POST",
				contentType: "application/json",
				dataType: 'json',
				data: JSON.stringify({
					id: parseInt($camid),
				})
			});
		}
	});
	
	/*
	 * move
	 */
	$('#move button.ptzmove').on('click touchstart mousedown', function($evt){
		if( $evt.type == 'click' ){
			moveClick($evt);
		} else {
			moveStart($evt);
		}
	});
	$('#move button.ptzstop').on('click touchstart mousedown', function($evt){
		moveStop();
	});
	$('#move button.ptzmove').on('touchend mouseup', function($evt){
		moveStop();
	});
	function moveStart($evt){
		$('#presets button').removeClass('active');
		$.ajax({
			url: "/camera/moveStart",
			type: "POST",
			contentType: "application/json",
			dataType: 'json',
			data: JSON.stringify({
				id: parseInt($camid),
				direction: $evt.currentTarget.id
			})
		});
	}
	function moveStop(){
		$('#presets button').removeClass('active');
		$.ajax({
			url: "/camera/moveStop",
			type: "POST",
			contentType: "application/json",
			dataType: 'json',
			data: JSON.stringify({
				id: parseInt($camid),
			})
		});
	}
	function moveClick($evt){
		moveStart($evt);
		stop = setTimeout(moveStop, 75);
	}

	/*
	 * user management
	 */
	$('#user .change').click( function(){
		$('#user .buttons').hide();
		$('#user .form').show();
	});

	$('#user .buttons .logout').click( function(){
		$.ajax({
			url: "/login/logout",
			type: "POST",
			success: function(){
				window.location.reload();
			}
		});
	});

	$('#user .form button').click( function(){
		$.ajax({
			url: "/login/setUser",
			type: "POST",
			contentType: "application/json",
			dataType: 'json',
			data: JSON.stringify({
				username: $('#user .form #current-username').val(),
				password: $('#user .form #current-password').val()
			}),
			success: function($response){
				if( $response.success ){
					$('#user .form').hide();
					$('#user .buttons').show();
				} else {
					//alert($response.error);
					alert("Gegevens niet opgeslagen.");
				}
			}
		});
	});
});