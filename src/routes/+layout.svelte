<script>
	import { io } from 'socket.io-client';
	import { spring } from 'svelte/motion';
	import PyodideWorker from '$lib/workers/pyodide.worker?worker';
	import { Toaster, toast } from 'svelte-sonner';

	let loadingProgress = spring(0, {
		stiffness: 0.05
	});

	import { onMount, tick, setContext, onDestroy } from 'svelte';
	import {
		config,
		user,
		settings,
		theme,
		WEBUI_NAME,
		WEBUI_VERSION,
		WEBUI_DEPLOYMENT_ID,
		mobile,
		socket,
		chatId,
		chats,
		currentChatPage,
		tags,
		temporaryChatEnabled,
		isLastActiveTab,
		isApp,
		appInfo,
		toolServers,
		playingNotificationSound,
		channels,
		channelId,
		terminalServers,
		showControls,
		showFileNavPath,
		showFileNavDir,
		pyodideWorker
	} from '$lib/stores';
	import { embedContext } from '$lib/stores/embedContext';
	import { geoportaalEmbed } from '$lib/stores/geoportaalEmbed';
	import {
		isAllowedHostOrigin,
		isHostFeatureClickedPayload,
		isHostVariantSwitchedPayload,
		parseHostEnvelope,
		sendToHost,
		BRIDGE_PROTOCOL_VERSION
	} from '$lib/bridge/geoportaal';
	import {
		getAllowedTokenOrigins,
		isAllowedTokenOrigin,
		parseClerkTokenClearedMessage,
		parseClerkTokenMessage,
		sendChatbotReady
	} from '$lib/bridge/clerkToken';
	import {
		clearBearerToken,
		getBearerToken,
		setBearerToken
	} from '$lib/stores/clerkBridge';
	import GeoportaalEmbedBanner from '$lib/components/embed/GeoportaalEmbedBanner.svelte';
	import { getFileContentById } from '$lib/apis/files';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { beforeNavigate } from '$app/navigation';
	import { updated } from '$app/state';

	import i18n, { initI18n, getLanguages, changeLanguage } from '$lib/i18n';

	import '../tailwind.css';
	import '../app.css';
	import 'tippy.js/dist/tippy.css';

	import { executeToolServer, getBackendConfig, getModels, getVersion } from '$lib/apis';
	import { dispatchDocGenToolCall } from '$lib/integrations/docGen/executeToolDispatch';
	import { getActiveDocGenClient, isDocGenServerUrl } from '$lib/integrations/docGen/store';
	import { getSessionUser, userSignOut } from '$lib/apis/auths';
	import { getAllTags, getChatList } from '$lib/apis/chats';
	import { chatCompletion } from '$lib/apis/openai';
	import {
		addOpenAIConnection,
		removeOpenAIConnection,
		addTerminalConnection,
		removeTerminalConnection
	} from '$lib/utils/connections';

	import { WEBUI_API_BASE_URL, WEBUI_BASE_URL, WEBUI_HOSTNAME } from '$lib/constants';
	import { bestMatchingLanguage, displayFileHandler } from '$lib/utils';
	import { setTextScale } from '$lib/utils/text-scale';

	import NotificationToast from '$lib/components/NotificationToast.svelte';
	import AppSidebar from '$lib/components/app/AppSidebar.svelte';
	import SyncStatsModal from '$lib/components/chat/Settings/SyncStatsModal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import { getUserSettings } from '$lib/apis/users';
	import dayjs from 'dayjs';
	import { getChannels } from '$lib/apis/channels';

	const unregisterServiceWorkers = async () => {
		if ('serviceWorker' in navigator) {
			try {
				const registrations = await navigator.serviceWorker.getRegistrations();
				await Promise.all(registrations.map((r) => r.unregister()));
				return true;
			} catch (error) {
				console.error('Error unregistering service workers:', error);
				return false;
			}
		}
		return false;
	};

	// handle frontend updates (https://svelte.dev/docs/kit/configuration#version)
	beforeNavigate(async ({ willUnload, to }) => {
		if (updated.current && !willUnload && to?.url) {
			await unregisterServiceWorkers();
			location.href = to.url.href;
		}
	});

	setContext('i18n', i18n);

	const bc = new BroadcastChannel('active-tab-channel');

	let loaded = false;
	let tokenTimer = null;

	let showRefresh = false;

	let showSyncStatsModal = false;
	let syncStatsEventData = null;

	let heartbeatInterval = null;

	const BREAKPOINT = 768;

	const setupSocket = async (enableWebsocket) => {
		const _socket = io(`${WEBUI_BASE_URL}` || undefined, {
			reconnection: true,
			reconnectionDelay: 1000,
			reconnectionDelayMax: 5000,
			randomizationFactor: 0.5,
			path: '/ws/socket.io',
			transports: enableWebsocket ? ['websocket'] : ['polling', 'websocket'],
			// Read the iframe-bridge bearer first (#145); fall back to
			// localStorage.token for the standalone tab + native-Clerk
			// paths. socket.io evaluates `auth` again on every reconnect,
			// so a token pushed mid-session is picked up by the explicit
			// disconnect/connect cycle in `windowMessageEventHandler`.
			auth: () => ({ token: getBearerToken() ?? localStorage.token })
		});
		await socket.set(_socket);

		_socket.on('connect_error', (err) => {
			console.log('connect_error', err);
		});

		_socket.on('connect', async () => {
			console.log('connected', _socket.id);
			const res = await getVersion(localStorage.token);

			const deploymentId = res?.deployment_id ?? null;
			const version = res?.version ?? null;

			if (version !== null || deploymentId !== null) {
				if (
					($WEBUI_VERSION !== null && version !== $WEBUI_VERSION) ||
					($WEBUI_DEPLOYMENT_ID !== null && deploymentId !== $WEBUI_DEPLOYMENT_ID)
				) {
					await unregisterServiceWorkers();
					location.href = location.href;
					return;
				}
			}

			// Send heartbeat every 30 seconds
			heartbeatInterval = setInterval(() => {
				if (_socket.connected) {
					console.log('Sending heartbeat');
					_socket.emit('heartbeat', {});
				}
			}, 30000);

			if (deploymentId !== null) {
				WEBUI_DEPLOYMENT_ID.set(deploymentId);
			}

			if (version !== null) {
				WEBUI_VERSION.set(version);
			}

			console.log('version', version);

			const authToken = getBearerToken() ?? localStorage.getItem('token');
			if (authToken) {
				// Emit user-join event with auth token (bridge bearer wins
				// over the localStorage fallback when the parent has pushed
				// a JWT via the rm:clerk-token handshake — #145).
				_socket.emit('user-join', { auth: { token: authToken } });
			} else {
				console.warn('No token found in bridge or localStorage, user-join event not emitted');
			}
		});

		_socket.on('reconnect_attempt', (attempt) => {
			console.log('reconnect_attempt', attempt);
		});

		_socket.on('reconnect_failed', () => {
			console.log('reconnect_failed');
		});

		_socket.on('disconnect', (reason, details) => {
			console.log(`Socket ${_socket.id} disconnected due to ${reason}`);

			if (heartbeatInterval) {
				clearInterval(heartbeatInterval);
				heartbeatInterval = null;
			}

			if (details) {
				console.log('Additional details:', details);
			}
		});
	};

	/**
	 * Get or create the persistent Pyodide worker.
	 * The worker persists across executions so the virtual FS (IDBFS) is preserved.
	 */
	const getOrCreateWorker = () => {
		let worker = $pyodideWorker;
		if (!worker) {
			worker = new PyodideWorker();
			pyodideWorker.set(worker);
		}
		return worker;
	};

	const executePythonAsWorker = async (id, code, cb, files = []) => {
		let result = null;
		let stdout = null;
		let stderr = null;

		let executing = true;
		let packages = [
			/\bimport\s+requests\b|\bfrom\s+requests\b/.test(code) ? 'requests' : null,
			/\bimport\s+bs4\b|\bfrom\s+bs4\b/.test(code) ? 'beautifulsoup4' : null,
			/\bimport\s+numpy\b|\bfrom\s+numpy\b/.test(code) ? 'numpy' : null,
			/\bimport\s+pandas\b|\bfrom\s+pandas\b/.test(code) ? 'pandas' : null,
			/\bimport\s+matplotlib\b|\bfrom\s+matplotlib\b/.test(code) ? 'matplotlib' : null,
			/\bimport\s+seaborn\b|\bfrom\s+seaborn\b/.test(code) ? 'seaborn' : null,
			/\bimport\s+sklearn\b|\bfrom\s+sklearn\b/.test(code) ? 'scikit-learn' : null,
			/\bimport\s+scipy\b|\bfrom\s+scipy\b/.test(code) ? 'scipy' : null,
			/\bimport\s+re\b|\bfrom\s+re\b/.test(code) ? 'regex' : null,
			/\bimport\s+seaborn\b|\bfrom\s+seaborn\b/.test(code) ? 'seaborn' : null,
			/\bimport\s+sympy\b|\bfrom\s+sympy\b/.test(code) ? 'sympy' : null,
			/\bimport\s+tiktoken\b|\bfrom\s+tiktoken\b/.test(code) ? 'tiktoken' : null,
			/\bimport\s+pytz\b|\bfrom\s+pytz\b/.test(code) ? 'pytz' : null
		].filter(Boolean);

		const worker = getOrCreateWorker();

		// Fetch file content from the server and prepare for the worker
		let filePayloads = [];
		if (files && files.length > 0) {
			for (const file of files) {
				try {
					const fileId = file?.id;
					const fileName = file?.filename || file?.name || 'file';
					if (fileId) {
						const content = await getFileContentById(fileId);
						if (content) {
							filePayloads.push({ name: fileName, data: content });
						}
					}
				} catch (e) {
					console.error('Failed to fetch file for Pyodide:', e);
				}
			}
		}

		worker.postMessage({
			type: 'execute',
			id: id,
			code: code,
			packages: packages,
			files: filePayloads.length > 0 ? filePayloads : undefined
		});

		// Timeout for this specific execution (not the worker itself)
		let timeoutId = setTimeout(() => {
			if (executing) {
				executing = false;
				stderr = 'Execution Time Limit Exceeded';

				// Terminate and recreate the worker on timeout
				worker.terminate();
				pyodideWorker.set(null);

				if (cb) {
					cb(
						JSON.parse(
							JSON.stringify(
								{
									stdout: stdout,
									stderr: stderr,
									result: result
								},
								(_key, value) => (typeof value === 'bigint' ? value.toString() : value)
							)
						)
					);
				}
			}
		}, 60000);

		// Use addEventListener so multiple concurrent executions don't clobber each other
		const onMessage = (event) => {
			const { id: eventId, ...data } = event.data;
			// Only handle responses for this execution ID
			if (eventId !== id) return;
			// Ignore FS responses (they use a type field)
			if (data.type && data.type.startsWith('fs:')) return;

			console.log('pyodideWorker.onmessage', event);
			clearTimeout(timeoutId);
			worker.removeEventListener('message', onMessage);
			worker.removeEventListener('error', onError);

			data['stdout'] && (stdout = data['stdout']);
			data['stderr'] && (stderr = data['stderr']);
			data['result'] && (result = data['result']);

			if (cb) {
				cb(
					JSON.parse(
						JSON.stringify(
							{
								stdout: stdout,
								stderr: stderr,
								result: result
							},
							(_key, value) => (typeof value === 'bigint' ? value.toString() : value)
						)
					)
				);
			}

			executing = false;
		};

		const onError = (event) => {
			console.log('pyodideWorker.onerror', event);
			clearTimeout(timeoutId);
			worker.removeEventListener('message', onMessage);
			worker.removeEventListener('error', onError);

			if (cb) {
				cb(
					JSON.parse(
						JSON.stringify(
							{
								stdout: stdout,
								stderr: stderr,
								result: result
							},
							(_key, value) => (typeof value === 'bigint' ? value.toString() : value)
						)
					)
				);
			}
			executing = false;
		};

		worker.addEventListener('message', onMessage);
		worker.addEventListener('error', onError);
	};

	const resolveToolServer = (serverUrl) => {
		let toolServer = $settings?.toolServers?.find((server) => server.url === serverUrl);
		if (!toolServer) {
			const terminalServer = ($settings?.terminalServers ?? []).find(
				(server) => server.url === serverUrl
			);
			if (terminalServer) {
				toolServer = {
					url: terminalServer.url,
					auth_type: terminalServer.auth_type ?? 'bearer',
					key: terminalServer.key ?? '',
					path: terminalServer.path ?? '/openapi.json'
				};
			}
		}

		let toolServerData =
			$toolServers?.find((server) => server.url === serverUrl) ??
			$terminalServers?.find((server) => server.url === serverUrl);

		let token = null;
		if (toolServer) {
			const auth_type = toolServer?.auth_type ?? 'bearer';
			if (auth_type === 'bearer') token = toolServer?.key;
			else if (auth_type === 'session') token = localStorage.token;
		}

		return { toolServer, toolServerData, token };
	};

	const executeTool = async (data, cb) => {
		// WI-014: route docgen_* tool calls to the active DG iframe client
		// instead of through executeToolServer (HTTP). The virtual URL
		// `rmdg-iframe://docgen` is not a real server — middleware.py
		// passes our tool_servers entry through, OWUI dispatches to here,
		// we hand it to the postMessage bridge.
		if (isDocGenServerUrl(data.server?.url)) {
			const client = getActiveDocGenClient();
			const result = await dispatchDocGenToolCall({
				client,
				toolName: data.name,
				params: data.params ?? {}
			});
			if (cb) {
				cb(structuredClone(result));
			}
			return;
		}

		const { toolServer, toolServerData, token } = resolveToolServer(data.server?.url);

		console.log('executeTool', data, toolServer);

		if (toolServer) {
			const res = await executeToolServer(
				token,
				toolServer.url,
				data?.name,
				data?.params,
				toolServerData
			);

			console.log('executeToolServer', res);

			if (data?.name === 'display_file' && data?.params?.path) {
				if (res?.exists !== false) {
					displayFileHandler(data.params.path, { showControls, showFileNavPath });
				}
			}

			if (['write_file'].includes(data?.name) && data?.params?.path) {
				showFileNavDir.set(res?.path ?? data.params.path);
			}

			if (cb) {
				cb(structuredClone(res));
			}
		} else {
			if (cb) {
				cb({ error: 'Tool Server Not Found' });
			}
		}
	};

	const chatEventHandler = async (event, cb) => {
		const chat = $page.url.pathname.includes(`/c/${event.chat_id}`);

		// Skip events from temporary chats that are not the current chat.
		// This prevents notifications from being sent to other tabs/devices
		// for privacy, since temporary chats are not meant to be persisted or visible elsewhere.
		const isTemporaryChat = event.chat_id?.startsWith('local:');
		if (isTemporaryChat && event.chat_id !== $chatId) {
			return;
		}

		let isFocused = document.visibilityState !== 'visible';
		if (window.electronAPI) {
			const res = await window.electronAPI.send({
				type: 'window:isFocused'
			});
			if (res) {
				isFocused = res.isFocused;
			}
		}

		await tick();
		const type = event?.data?.type ?? null;
		const data = event?.data?.data ?? null;

		if ((event.chat_id !== $chatId && !$temporaryChatEnabled) || isFocused) {
			if (type === 'chat:completion') {
				const { done, content, title } = data;
				const displayTitle = title || $i18n.t('New Chat');

				if (done) {
					if ($settings?.notificationSoundAlways ?? false) {
						playingNotificationSound.set(true);

						const audio = new Audio(`/audio/notification.mp3`);
						audio.play().finally(() => {
							// Ensure the global state is reset after the sound finishes
							playingNotificationSound.set(false);
						});
					}

					if ($isLastActiveTab) {
						if ($settings?.notificationEnabled ?? false) {
							new Notification(`${displayTitle} • Open WebUI`, {
								body: content,
								icon: `${WEBUI_BASE_URL}/brand-assets/icon-blue.png`
							});
						}
					}

					toast.custom(NotificationToast, {
						componentProps: {
							onClick: () => {
								goto(`/c/${event.chat_id}`);
							},
							content: content,
							title: displayTitle
						},
						duration: 15000,
						unstyled: true
					});
				}
			} else if (type === 'chat:title') {
				currentChatPage.set(1);
				await chats.set(await getChatList(localStorage.token, $currentChatPage));
			} else if (type === 'chat:tags') {
				tags.set(await getAllTags(localStorage.token));
			}
		} else if (data?.session_id === $socket.id) {
			if (type === 'execute:python') {
				console.log('execute:python', data);
				executePythonAsWorker(data.id, data.code, cb, data.files || []);
			} else if (type === 'execute:tool') {
				console.log('execute:tool', data);
				executeTool(data, cb);
			} else if (type === 'request:chat:completion') {
				console.log(data, $socket.id);
				const { session_id, channel, form_data, model } = data;

				try {
					const directConnections = $settings?.directConnections ?? {};

					if (directConnections) {
						const urlIdx = model?.urlIdx;

						const OPENAI_API_URL = directConnections.OPENAI_API_BASE_URLS[urlIdx];
						const OPENAI_API_KEY = directConnections.OPENAI_API_KEYS[urlIdx];
						const API_CONFIG = directConnections.OPENAI_API_CONFIGS[urlIdx];

						try {
							if (API_CONFIG?.prefix_id) {
								const prefixId = API_CONFIG.prefix_id;
								form_data['model'] = form_data['model'].replace(`${prefixId}.`, ``);
							}

							const [res, controller] = await chatCompletion(
								OPENAI_API_KEY,
								form_data,
								OPENAI_API_URL
							);

							if (res) {
								// raise if the response is not ok
								if (!res.ok) {
									throw await res.json();
								}

								if (form_data?.stream ?? false) {
									cb({
										status: true
									});
									console.log({ status: true });

									// res will either be SSE or JSON
									const reader = res.body.getReader();
									const decoder = new TextDecoder();

									const processStream = async () => {
										while (true) {
											// Read data chunks from the response stream
											const { done, value } = await reader.read();
											if (done) {
												break;
											}

											// Decode the received chunk
											const chunk = decoder.decode(value, { stream: true });

											// Process lines within the chunk
											const lines = chunk.split('\n').filter((line) => line.trim() !== '');

											for (const line of lines) {
												console.log(line);
												$socket?.emit(channel, line);
											}
										}
									};

									// Process the stream in the background
									await processStream();
								} else {
									const data = await res.json();
									cb(data);
								}
							} else {
								throw new Error('An error occurred while fetching the completion');
							}
						} catch (error) {
							console.error('chatCompletion', error);
							cb(error);
						}
					}
				} catch (error) {
					console.error('chatCompletion', error);
					cb(error);
				} finally {
					$socket.emit(channel, {
						done: true
					});
				}
			} else {
				console.log('chatEventHandler', event);
			}
		}
	};

	const channelEventHandler = async (event) => {
		console.log('channelEventHandler', event);
		if (event.data?.type === 'typing') {
			return;
		}

		// handle channel created event
		if (event.data?.type === 'channel:created') {
			const res = await getChannels(localStorage.token).catch(async (error) => {
				return null;
			});

			if (res) {
				await channels.set(
					res.sort(
						(a, b) =>
							['', null, 'group', 'dm'].indexOf(a.type) - ['', null, 'group', 'dm'].indexOf(b.type)
					)
				);
			}

			return;
		}

		// check url path
		const channel = $page.url.pathname.includes(`/channels/${event.channel_id}`);

		let isFocused = document.visibilityState !== 'visible';
		if (window.electronAPI) {
			const res = await window.electronAPI.send({
				type: 'window:isFocused'
			});
			if (res) {
				isFocused = res.isFocused;
			}
		}

		if ((!channel || isFocused) && event?.user?.id !== $user?.id) {
			await tick();
			const type = event?.data?.type ?? null;
			const data = event?.data?.data ?? null;

			if ($channels) {
				if ($channels.find((ch) => ch.id === event.channel_id) && $channelId !== event.channel_id) {
					channels.set(
						$channels.map((ch) => {
							if (ch.id === event.channel_id) {
								if (type === 'message') {
									return {
										...ch,
										unread_count: (ch.unread_count ?? 0) + 1,
										last_message_at: event.created_at
									};
								}
							}
							return ch;
						})
					);
				} else {
					const res = await getChannels(localStorage.token).catch(async (error) => {
						return null;
					});

					if (res) {
						await channels.set(
							res.sort(
								(a, b) =>
									['', null, 'group', 'dm'].indexOf(a.type) -
									['', null, 'group', 'dm'].indexOf(b.type)
							)
						);
					}
				}
			}

			if (type === 'message') {
				const title = `${data?.user?.name}${event?.channel?.type !== 'dm' ? ` (#${event?.channel?.name})` : ''}`;

				if ($isLastActiveTab) {
					if ($settings?.notificationEnabled ?? false) {
						new Notification(`${title} • Open WebUI`, {
							body: data?.content,
							icon: `${WEBUI_API_BASE_URL}/users/${data?.user?.id}/profile/image`
						});
					}
				}

				toast.custom(NotificationToast, {
					componentProps: {
						onClick: () => {
							goto(`/channels/${event.channel_id}`);
						},
						content: data?.content,
						title: `${title}`
					},
					duration: 15000,
					unstyled: true
				});
			}
		}
	};

	const TOKEN_EXPIRY_BUFFER = 60; // seconds
	const checkTokenExpiry = async () => {
		const exp = $user?.expires_at; // token expiry time in unix timestamp
		const now = Math.floor(Date.now() / 1000); // current time in unix timestamp

		if (!exp) {
			// If no expiry time is set, do nothing
			return;
		}

		if (now >= exp - TOKEN_EXPIRY_BUFFER) {
			const res = await userSignOut();
			user.set(null);
			localStorage.removeItem('token');

			location.href = res?.redirect_url ?? '/auth';
		}
	};

	const desktopEventHandler = async (event) => {
		// Events that don't require auth
		if (event.type === 'page:reload') {
			location.reload();
			return;
		}
		if (event.type === 'page:navigate' && event.data?.path) {
			await goto(event.data.path);
			return;
		}
		if (event.type === 'models:refresh') {
			const token = localStorage.token;
			if (token) {
				models.set(
					await getModels(
						token,
						$config?.features?.enable_direct_connections
							? ($settings?.directConnections ?? null)
							: null
					)
				);
			}
			return;
		}

		const token = localStorage.token;
		if (!token) return;

		// Only admins can modify system-level connections
		if ($user?.role !== 'admin') return;

		try {
			if (event.type === 'connections:terminal') {
				if (event.data.action === 'add') {
					await addTerminalConnection(token, {
						url: event.data.url,
						key: event.data.key,
						name: 'Local Open Terminal'
					});
				} else if (event.data.action === 'remove') {
					await removeTerminalConnection(token, event.data.url);
				}
			} else if (event.type === 'connections:openai') {
				if (event.data.action === 'add') {
					await addOpenAIConnection(token, {
						url: event.data.url,
						key: event.data.key
					});
				} else if (event.data.action === 'remove') {
					await removeOpenAIConnection(token, event.data.url);
				}
			}
		} catch (e) {
			console.error('Desktop connection update failed:', e);
		}
	};

	// Origins allowed to talk to this SPA via window.postMessage. Includes the
	// Open WebUI marketing site (export:stats handshake) and the Ruimtemeesters
	// Databank app (rm:chatbot:context handshake when this SPA is iframed inside
	// the Databank document detail page).
	const OPENWEBUI_MESSAGE_ORIGINS = [
		'https://openwebui.com',
		'https://www.openwebui.com',
		'http://localhost:9999'
	];
	const RM_DATABANK_ORIGINS = [
		'https://databank.datameesters.nl',
		'https://databank.staging.datameesters.nl',
		'http://localhost:5173',
		'http://localhost:5050'
	];
	// Geoportaal uses the typed PRD-0023 envelope protocol; the host
	// origins live alongside Databank's because the chatbot can be
	// iframed by either app. Detection happens on `event.data` shape
	// — Databank uses `type: 'rm:chatbot:context'`, Geoportaal uses
	// `protocolVersion: 1` with a typed `host.*` discriminator.
	const RM_GEOPORTAAL_ORIGINS = [
		'https://geoportaal.datameesters.nl',
		'https://digitaltwin.datameesters.nl',
		'https://geoportaal-staging.datameesters.nl',
		'http://localhost:3000',
		// Match `ALLOWED_HOST_ORIGINS` in `$lib/bridge/geoportaal.ts` so the
		// outer message-gate doesn't depend on Databank's list happening
		// to also include localhost:5173 (Bugbot finding on PR #42).
		'http://localhost:5173'
	];
	const ALLOWED_MESSAGE_ORIGINS = [
		...OPENWEBUI_MESSAGE_ORIGINS,
		...RM_DATABANK_ORIGINS,
		...RM_GEOPORTAAL_ORIGINS,
		// Clerk-Bearer handshake (#145). Single source of truth lives
		// in $lib/bridge/clerkToken.ts; mirroring here keeps the outer
		// origin-gate from blocking valid token pushes from origins
		// that aren't otherwise allowlisted (e.g. datameesters.nl).
		...getAllowedTokenOrigins()
	];

	const windowMessageEventHandler = async (event) => {
		if (!ALLOWED_MESSAGE_ORIGINS.includes(event.origin)) {
			return;
		}

		// export:stats is the OpenWebUI marketing-site handshake; restrict to its
		// trusted origins so Databank embeds (which share ALLOWED_MESSAGE_ORIGINS
		// for the rm:chatbot:context handshake below) cannot trigger the modal.
		if (
			(event.data === 'export:stats' || event.data?.type === 'export:stats') &&
			OPENWEBUI_MESSAGE_ORIGINS.includes(event.origin)
		) {
			syncStatsEventData = event.data;
			showSyncStatsModal = true;
			return;
		}

		// Clerk-Bearer handshake (#145, M1 of the iframe-bridge programme).
		// The parent pushes a Clerk session JWT; we hold it in module-level
		// memory and forward it as `Authorization: Bearer` on fetch + the
		// Socket.IO handshake. Origin is double-checked against the
		// token-specific allowlist (the outer ALLOWED_MESSAGE_ORIGINS includes
		// other protocols' origins that must NOT be allowed to push tokens).
		if (event.data?.type === 'rm:clerk-token' && isAllowedTokenOrigin(event.origin)) {
			const payload = parseClerkTokenMessage(event.data);
			if (payload) {
				setBearerToken(payload.token);
				// Force a socket reconnect so the new auth payload fires.
				// No-op when the socket hasn't been created yet — the
				// initial setupSocket call below will pick up the token
				// from module-level memory.
				const live = $socket;
				if (live) {
					live.disconnect();
					live.connect();
				}
			}
			return;
		}
		if (
			event.data?.type === 'rm:clerk-token-cleared' &&
			isAllowedTokenOrigin(event.origin)
		) {
			if (parseClerkTokenClearedMessage(event.data)) {
				clearBearerToken();
				const live = $socket;
				if (live) {
					live.disconnect();
					live.connect();
				}
			}
			return;
		}

		// Ruimtemeesters Databank tells us which document the user is currently
		// viewing in the parent app. We mirror it into a store so chat pages can
		// seed system prompts or render a context banner.
		if (event.data?.type === 'rm:chatbot:context' && RM_DATABANK_ORIGINS.includes(event.origin)) {
			const payload = event.data.payload;
			if (payload && typeof payload === 'object' && typeof payload.documentId === 'string') {
				embedContext.set({
					documentId: payload.documentId,
					source: payload.source ?? null,
					documentType: payload.documentType ?? null,
					publisher: payload.publisher ?? null,
					title: payload.title ?? null
				});
			}
		}

		// Ruimtemeesters Geoportaal — typed PRD-0023 envelope protocol.
		// We accept only `source: 'host'` envelopes (no spoofed iframe.*
		// from a host origin). The parser also enforces protocolVersion,
		// projectId/variantId presence, and payload-shape.
		if (
			event.data?.protocolVersion === BRIDGE_PROTOCOL_VERSION &&
			isAllowedHostOrigin(event.origin)
		) {
			const env = parseHostEnvelope(event.data);
			if (!env) return;
			// Drop the message entirely when we haven't detected a live
			// Geoportaal embed (referrer-detect failed, or the chatbot is
			// running standalone). Without this gate the handlers below
			// would still mutate the store with `state.active === false`
			// and `projectId === NaN`, corrupting future embed-detection.
			// Bugbot finding on PR #42 (Missing active-state guard).
			const state = $geoportaalEmbed;
			if (!state.active) return;
			// Drop messages addressed to a different project than the iframe
			// was instantiated for — defends against host bugs that could
			// cross-talk between project tabs. Variant-mismatch is exempt
			// for `host.variant.switched`: that envelope by definition
			// carries the NEW variantId while our store still has the OLD
			// one, so guarding on variantId would silently drop the very
			// event meant to update the store.
			if (env.projectId !== state.projectId) return;
			if (env.type !== 'host.variant.switched' && env.variantId !== state.variantId) {
				return;
			}
			if (env.type === 'host.ready') {
				geoportaalEmbed.update((s) => ({ ...s, bridgeState: 'ready' }));
				return;
			}
			if (env.type === 'host.feature.clicked') {
				if (!isHostFeatureClickedPayload(env.payload)) return;
				const payload = env.payload;
				geoportaalEmbed.update((s) => ({ ...s, lastFeature: payload }));
				return;
			}
			if (env.type === 'host.variant.switched') {
				if (!isHostVariantSwitchedPayload(env.payload)) return;
				const payload = env.payload;
				geoportaalEmbed.update((s) => ({ ...s, variantId: payload.variantId }));
				return;
			}
			// Unknown host.* events are silently ignored (forward-compat).
		}
	};

	onMount(async () => {
		window.addEventListener('message', windowMessageEventHandler);

		// Install the fetch proxy that injects the bridge bearer (#145).
		// Same-origin only — never leaks the Clerk JWT to external URLs
		// (images, third-party APIs). When no bridge token is set this is
		// a pure pass-through, so standalone-tab + Geoportaal-native paths
		// are unaffected.
		if (typeof window !== 'undefined' && !window.__rmFetchProxyInstalled) {
			const originalFetch = window.fetch.bind(window);
			window.fetch = async (input, init) => {
				const token = getBearerToken();
				if (!token) return originalFetch(input, init);
				let url;
				try {
					url =
						input instanceof Request
							? new URL(input.url, window.location.origin)
							: new URL(String(input), window.location.origin);
				} catch {
					return originalFetch(input, init);
				}
				if (url.origin !== window.location.origin) {
					return originalFetch(input, init);
				}
				const headers = new Headers(
					init?.headers ?? (input instanceof Request ? input.headers : undefined)
				);
				headers.set('Authorization', `Bearer ${token}`);
				const next = { ...(init ?? {}), headers };
				if (input instanceof Request) {
					return originalFetch(new Request(input, next));
				}
				return originalFetch(input, next);
			};
			window.__rmFetchProxyInstalled = true;
		}

		// If we're inside an iframe, signal the parent that we're ready so it
		// can post the document context. Used by the Ruimtemeesters Databank
		// embed; harmless no-op when we're top-level.
		if (typeof window !== 'undefined' && window.parent && window.parent !== window) {
			try {
				window.parent.postMessage({ type: 'rm:chatbot:ready' }, '*');
			} catch (e) {
				console.debug('rm:chatbot:ready postMessage failed:', e);
			}

			// Clerk-Bearer handshake (#145). Distinct message type from
			// the Databank `rm:chatbot:ready` colon-form above (which is
			// the legacy Databank handshake — broadcast to '*' for back-
			// compat). The hyphen-form `rm:chatbot-ready` is targeted to
			// the allowlisted parent origin only, per ADR-0025's no-broadcast
			// rule.
			let parentOrigin = '';
			try {
				parentOrigin = new URL(document.referrer || '').origin;
			} catch {
				parentOrigin = '';
			}
			if (parentOrigin && isAllowedTokenOrigin(parentOrigin)) {
				sendChatbotReady(parentOrigin, $WEBUI_VERSION ?? 'unknown');
			}
		}

		// Ruimtemeesters Geoportaal embed-detection — see ADR-0021 in the
		// Geoportaal repo. Markers: URL has ?projectId, we're in iframe,
		// referrer is from a Geoportaal origin. When all three line up,
		// populate the embed-store and emit `iframe.ready` per PRD-0023.
		if (typeof window !== 'undefined' && window.parent && window.parent !== window) {
			const params = new URLSearchParams(window.location.search);
			const projectIdRaw = params.get('projectId');
			if (projectIdRaw) {
				const projectId = Number.parseInt(projectIdRaw, 10);
				const variantId = params.get('variantId') ?? 'baseline';
				let hostOrigin = '';
				try {
					hostOrigin = new URL(document.referrer || '').origin;
				} catch {
					hostOrigin = '';
				}
				if (Number.isFinite(projectId) && projectId > 0 && isAllowedHostOrigin(hostOrigin)) {
					geoportaalEmbed.set({
						active: true,
						projectId,
						variantId,
						hostOrigin,
						bridgeState: 'pending',
						lastFeature: null
					});
					sendToHost(
						'iframe.ready',
						{ iframeVersion: '1.0.0' },
						{ projectId, variantId, hostOrigin }
					);
				}
			}
		}

		let touchstartY = 0;

		function isNavOrDescendant(el) {
			const nav = document.querySelector('nav'); // change selector if needed
			return nav && (el === nav || nav.contains(el));
		}

		const touchstartHandler = (e) => {
			if (!isNavOrDescendant(e.target)) return;
			touchstartY = e.touches[0].clientY;
		};

		const touchmoveHandler = (e) => {
			if (!isNavOrDescendant(e.target)) return;
			const touchY = e.touches[0].clientY;
			const touchDiff = touchY - touchstartY;
			if (touchDiff > 50 && window.scrollY === 0) {
				showRefresh = true;
				e.preventDefault();
			}
		};

		const touchendHandler = (e) => {
			if (!isNavOrDescendant(e.target)) return;
			if (showRefresh) {
				showRefresh = false;
				location.reload();
			}
		};

		document.addEventListener('touchstart', touchstartHandler);
		document.addEventListener('touchmove', touchmoveHandler, { passive: false });
		document.addEventListener('touchend', touchendHandler);

		if (typeof window !== 'undefined') {
			if (window.applyTheme) {
				window.applyTheme();
			}
		}

		if (window?.electronAPI) {
			const info = await window.electronAPI.send({
				type: 'app:info'
			});

			if (info) {
				isApp.set(true);
				appInfo.set(info);

				const data = await window.electronAPI.send({
					type: 'app:data'
				});

				if (data) {
					appData.set(data);
				}
			}

			// Listen for desktop service lifecycle events (scalable protocol)
			if (window.electronAPI.onEvent) {
				window.electronAPI.onEvent(desktopEventHandler);
			}
		}

		// Listen for messages on the BroadcastChannel
		bc.onmessage = (event) => {
			if (event.data === 'active') {
				isLastActiveTab.set(false); // Another tab became active
			}
		};

		// Set yourself as the last active tab when this tab is focused
		const handleVisibilityChange = () => {
			if (document.visibilityState === 'visible') {
				isLastActiveTab.set(true); // This tab is now the active tab
				bc.postMessage('active'); // Notify other tabs that this tab is active

				// Check token expiry when the tab becomes active
				checkTokenExpiry();
			}
		};

		// Add event listener for visibility state changes
		document.addEventListener('visibilitychange', handleVisibilityChange);

		// Call visibility change handler initially to set state on load
		handleVisibilityChange();

		theme.set(localStorage.theme);

		mobile.set(window.innerWidth < BREAKPOINT);

		const onResize = () => {
			if (window.innerWidth < BREAKPOINT) {
				mobile.set(true);
			} else {
				mobile.set(false);
			}
		};
		window.addEventListener('resize', onResize);

		user.subscribe(async (value) => {
			if (value) {
				$socket?.off('events', chatEventHandler);
				$socket?.off('events:channel', channelEventHandler);

				$socket?.on('events', chatEventHandler);
				$socket?.on('events:channel', channelEventHandler);

				const userSettings = await getUserSettings(localStorage.token);
				if (userSettings) {
					settings.set(userSettings.ui);
				} else {
					settings.set(JSON.parse(localStorage.getItem('settings') ?? '{}'));
				}
				setTextScale($settings?.textScale ?? 1);

				// Set up the token expiry check
				if (tokenTimer) {
					clearInterval(tokenTimer);
				}
				tokenTimer = setInterval(checkTokenExpiry, 15000);
			} else {
				$socket?.off('events', chatEventHandler);
				$socket?.off('events:channel', channelEventHandler);
			}
		});

		let backendConfig = null;
		try {
			backendConfig = await getBackendConfig();
			console.log('Backend config:', backendConfig);
		} catch (error) {
			if (error?.authRedirect) {
				// Forward-auth proxy is redirecting to an external login page.
				// Full-page navigation lets the browser follow the redirect natively.
				window.location.href = '/';
				return;
			}
			console.error('Error loading backend config:', error);
		}
		// Initialize i18n even if we didn't get a backend config,
		// so `/error` can show something that's not `undefined`.

		// Prefer the server-configured DEFAULT_LOCALE (compose env) over the
		// user's previously-cached locale. When the deployment chose a language
		// for users, initI18n hard-overrides localStorage so returning visitors
		// don't keep an old en-US that browser auto-detect or a stale picker
		// put there. Without this, the override added in d12ddb62a never fires
		// for returning users because initI18n receives the *user's* cached
		// locale instead of the deployment's policy.
		initI18n(backendConfig?.default_locale || undefined);
		if (!localStorage.locale && !backendConfig?.default_locale) {
			const languages = await getLanguages();
			const browserLanguages = navigator.languages
				? navigator.languages
				: [navigator.language || navigator.userLanguage];
			const lang = bestMatchingLanguage(languages, browserLanguages, 'en-US');
			changeLanguage(lang);
			dayjs.locale(lang);
		}

		if (backendConfig) {
			// Save Backend Status to Store
			await config.set(backendConfig);
			await WEBUI_NAME.set(backendConfig.name);

			if ($config) {
				await setupSocket($config.features?.enable_websocket ?? true);

				const currentUrl = `${window.location.pathname}${window.location.search}`;
				const encodedUrl = encodeURIComponent(currentUrl);

				if (localStorage.token) {
					// Get Session User Info
					const sessionUser = await getSessionUser(localStorage.token).catch((error) => {
						toast.error(`${error}`);
						return null;
					});

					if (sessionUser) {
						await user.set(sessionUser);
						try {
							await config.set(await getBackendConfig());
						} catch (error) {
							console.error('Error refreshing backend config:', error);
						}
					} else {
						// Redirect Invalid Session User to /auth Page
						localStorage.removeItem('token');
						await goto(`/auth?redirect=${encodedUrl}`);
					}
				} else {
					// Don't redirect if we're already on the auth page
					// Needed because we pass in tokens from OAuth logins via URL fragments
					if ($page.url.pathname !== '/auth') {
						await goto(`/auth?redirect=${encodedUrl}`);
					}
				}
			}
		} else {
			// Redirect to /error when Backend Not Detected
			await goto(`/error`);
		}

		await tick();

		if (
			document.documentElement.classList.contains('her') &&
			document.getElementById('progress-bar')
		) {
			loadingProgress.subscribe((value) => {
				const progressBar = document.getElementById('progress-bar');

				if (progressBar) {
					progressBar.style.width = `${value}%`;
				}
			});

			await loadingProgress.set(100);

			document.getElementById('splash-screen')?.remove();

			const audio = new Audio(`/audio/greeting.mp3`);
			const playAudio = () => {
				audio.play();
				document.removeEventListener('click', playAudio);
			};

			document.addEventListener('click', playAudio);

			loaded = true;
		} else {
			document.getElementById('splash-screen')?.remove();
			loaded = true;
		}

		// Auto-show SyncStatsModal when opened with ?sync=true (from community)
		if (
			(window.opener ?? false) &&
			$page.url.searchParams.get('sync') === 'true' &&
			($config?.features?.enable_community_sharing ?? false)
		) {
			showSyncStatsModal = true;
		}

		return () => {
			window.removeEventListener('resize', onResize);
			window.removeEventListener('message', windowMessageEventHandler);
			document.removeEventListener('touchstart', touchstartHandler);
			document.removeEventListener('touchmove', touchmoveHandler);
			document.removeEventListener('touchend', touchendHandler);
			document.removeEventListener('visibilitychange', handleVisibilityChange);
		};
	});

	onDestroy(() => {
		bc.close();
	});
</script>

<svelte:head>
	<title>{$WEBUI_NAME}</title>
	<link crossorigin="anonymous" rel="icon" href="{WEBUI_BASE_URL}/brand-assets/icon-blue.png" />

	<meta name="apple-mobile-web-app-title" content={$WEBUI_NAME} />
	<meta name="description" content={$WEBUI_NAME} />
	<link
		rel="search"
		type="application/opensearchdescription+xml"
		title={$WEBUI_NAME}
		href="/opensearch.xml"
		crossorigin="use-credentials"
	/>
</svelte:head>

{#if showRefresh}
	<div class=" py-5">
		<Spinner className="size-5" />
	</div>
{/if}

{#if loaded}
	{#if $embedContext}
		<!-- Banner shown when this SPA is embedded inside the Ruimtemeesters
		     Databank app and the parent has told us which document the user is
		     reading. Lets the user see the integration is alive without changing
		     the rest of the chat surface. The banner is fixed (so it stays put
		     while the chat scrolls) — the wrapper below adds matching top
		     padding so the chat surface isn't covered. -->
		<div
			class="fixed top-0 inset-x-0 z-50 bg-blue-50 dark:bg-blue-950/60 border-b border-blue-200 dark:border-blue-800 px-4 py-2 text-xs text-blue-900 dark:text-blue-100 flex items-center justify-between gap-3"
		>
			<div class="truncate">
				<span class="font-medium">Beleidsdocument in beeld:</span>
				<span class="ml-1 truncate">{$embedContext.title ?? $embedContext.documentId}</span>
				{#if $embedContext.publisher}
					<span class="ml-2 opacity-75">· {$embedContext.publisher}</span>
				{/if}
			</div>
			<button
				type="button"
				class="text-blue-700 dark:text-blue-300 hover:underline shrink-0"
				on:click={() => embedContext.set(null)}
			>
				sluiten
			</button>
		</div>
	{/if}

	<!-- Geoportaal embed-banner — only renders when this SPA is iframed
	     inside Geoportaal (`?projectId=…` URL marker + Geoportaal-allowlisted
	     referrer). Standalone use is unaffected; banner stays hidden. -->
	<GeoportaalEmbedBanner />

	<div class:pt-9={$embedContext}>
		{#if $isApp}
			<div class="flex flex-row h-screen">
				<AppSidebar />

				<div class="w-full flex-1 max-w-[calc(100%-4.5rem)]">
					<slot />
				</div>
			</div>
		{:else}
			<slot />
		{/if}
	</div>
{/if}

{#if $config?.features.enable_community_sharing}
	<SyncStatsModal bind:show={showSyncStatsModal} eventData={syncStatsEventData} />
{/if}

<Toaster
	theme={$theme.includes('dark')
		? 'dark'
		: $theme === 'system'
			? window.matchMedia('(prefers-color-scheme: dark)').matches
				? 'dark'
				: 'light'
			: 'light'}
	richColors
	position="top-right"
	closeButton
/>
