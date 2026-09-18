(() => {
  const app = document.getElementById('wordRunnerApp');
  if (!app) return;

  const canvas = document.getElementById('runnerCanvas');
  const ctx = canvas.getContext('2d');
  const startOverlay = document.getElementById('gameStartOverlay');
  const endOverlay = document.getElementById('gameEndOverlay');
  const challengeOverlay = document.getElementById('challengeOverlay');
  const startButton = document.getElementById('startRunButton');
  const playAgainButton = document.getElementById('playAgainButton');
  const jumpButton = document.getElementById('jumpButton');
  const continueButton = document.getElementById('challengeContinue');

  const urlForRun = (template, runId) => template.replace('/0/', `/${runId}/`);
  const urlForAnswer = (template, runId, challengeId) =>
    template.replace('/0/', `/${runId}/`).replace('/0/answer', `/${challengeId}/answer`);

  const state = {
    runId: null,
    active: false,
    paused: true,
    finishing: false,
    challengePending: false,
    currentChallenge: null,
    rescueChallenge: false,
    scenario: { key: 'meadow', label: 'Green Valley' },
    lastTs: 0,
    distance: 0,
    targetDistance: 1700,
    energy: 100,
    score: 0,
    tier: 1,
    level: 'A1',
    speed: 68,
    energyDrain: .42,
    obstacleGap: 430,
    challengeInterval: 470,
    nextChallengeAt: 470,
    nextObstacleAt: 520,
    obstacles: [],
    platforms: [],
    particles: [],
    invincibleUntil: 0,
    player: { x: 145, y: 302, w: 34, h: 48, vy: 0, grounded: true },
  };

  function updateHud() {
    document.getElementById('gameTier').textContent = state.tier;
    document.getElementById('gameLevel').textContent = state.level;
    document.getElementById('distanceText').textContent = Math.floor(state.distance);
    document.getElementById('targetDistance').textContent = state.targetDistance;
    document.getElementById('scoreText').textContent = state.score;
    const energy = Math.max(0, Math.min(100, state.energy));
    document.getElementById('energyText').textContent = `${Math.round(energy)}%`;
    const bar = document.getElementById('energyBar');
    bar.style.width = `${energy}%`;
    if (energy < 30) bar.style.background = 'linear-gradient(90deg,#f04438,#f79009)';
    else if (energy < 60) bar.style.background = 'linear-gradient(90deg,#f79009,#fdb022)';
    else bar.style.background = 'linear-gradient(90deg,#10b981,#84cc16)';
  }

  async function jsonFetch(url, options = {}) {
    const response = await fetch(url, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.ok === false) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }

  function resetWorld(config) {
    state.runId = config.run_id;
    state.active = true;
    state.paused = false;
    state.finishing = false;
    state.challengePending = false;
    state.currentChallenge = null;
    state.rescueChallenge = false;
    state.distance = 0;
    state.targetDistance = config.target_distance;
    state.energy = 100;
    state.score = 0;
    state.tier = config.tier;
    state.level = config.level_code;
    state.speed = 68 * config.speed_multiplier;
    state.energyDrain = config.energy_drain;
    state.scenario = config.scenario || { key: 'meadow', label: 'Green Valley' };
    const scenarioBadge = document.getElementById('scenarioBadge');
    if (scenarioBadge) scenarioBadge.textContent = state.scenario.label || 'Route';
    state.obstacleGap = config.obstacle_gap;
    state.challengeInterval = config.challenge_interval;
    state.nextChallengeAt = config.challenge_interval;
    state.nextObstacleAt = 480;
    state.obstacles = [];
    state.platforms = [];
    state.particles = [];
    state.player.y = 302;
    state.player.vy = 0;
    state.player.grounded = true;
    state.invincibleUntil = 0;
    state.lastTs = performance.now();
    startOverlay.classList.remove('is-visible');
    endOverlay.classList.remove('is-visible');
    challengeOverlay.classList.remove('is-visible');
    updateHud();
    requestAnimationFrame(loop);
  }

  async function startRun() {
    if (startButton) startButton.disabled = true;
    app.classList.add('game-loading');
    try {
      const config = await jsonFetch(app.dataset.startUrl, { method: 'POST', body: '{}' });
      resetWorld(config);
    } catch (error) {
      alert(`Could not start the game: ${error.message}`);
    } finally {
      app.classList.remove('game-loading');
      if (startButton) startButton.disabled = false;
    }
  }

  function jump() {
    if (!state.active || state.paused) return;
    if (state.player.grounded) {
      state.player.vy = -455;
      state.player.grounded = false;
    }
  }

  function spawnWorld() {
    while (state.nextObstacleAt < state.distance + 1100) {
      const height = 20 + Math.random() * 28;
      state.obstacles.push({ at: state.nextObstacleAt, w: 26 + Math.random() * 16, h: height });
      if (Math.random() > .48) {
        state.platforms.push({ at: state.nextObstacleAt + 125, w: 105 + Math.random() * 55, y: 255 - Math.random() * 55 });
      }
      state.nextObstacleAt += state.obstacleGap * (.82 + Math.random() * .4);
    }
    state.obstacles = state.obstacles.filter(o => o.at > state.distance - 250);
    state.platforms = state.platforms.filter(p => p.at + p.w > state.distance - 250);
  }

  function screenX(at) {
    return state.player.x + (at - state.distance);
  }

  function collideObstacle(now) {
    if (now < state.invincibleUntil) return;
    const p = state.player;
    for (const o of state.obstacles) {
      const x = screenX(o.at);
      const y = 350 - o.h;
      if (x < p.x + p.w && x + o.w > p.x && y < p.y + p.h && y + o.h > p.y) {
        state.energy -= 13;
        state.invincibleUntil = now + 1100;
        state.player.vy = -300;
        state.player.grounded = false;
        for (let i = 0; i < 10; i++) state.particles.push({ x: p.x + 15, y: p.y + 22, vx: -70 + Math.random() * 140, vy: -90 + Math.random() * 120, life: 1 });
        break;
      }
    }
  }

  function physics(dt, now) {
    const p = state.player;
    const previousBottom = p.y + p.h;
    p.vy += 1250 * dt;
    p.y += p.vy * dt;
    p.grounded = false;

    let floorY = 350;
    for (const platform of state.platforms) {
      const x = screenX(platform.at);
      if (x < p.x + p.w && x + platform.w > p.x && p.vy >= 0) {
        const platformY = platform.y;
        if (previousBottom <= platformY + 8 && p.y + p.h >= platformY) {
          floorY = Math.min(floorY, platformY);
        }
      }
    }

    if (p.y + p.h >= floorY) {
      p.y = floorY - p.h;
      p.vy = 0;
      p.grounded = true;
    }
    collideObstacle(now);
  }

  const SCENE_PALETTES = {
    meadow: {
      skyTop: '#dff4ff', skyBottom: '#f8fbff', hill: '#c7e8d5',
      ground: '#98d6b3', groundTop: '#6eb28d', obstacle: '#7c3aed',
      obstacleAccent: '#a78bfa', platform: '#475467', platformAccent: '#667085'
    },
    sunset: {
      skyTop: '#ffcfad', skyBottom: '#fff4df', hill: '#d8a06f',
      ground: '#8c6a62', groundTop: '#694f49', obstacle: '#c2410c',
      obstacleAccent: '#fb923c', platform: '#5f514b', platformAccent: '#8a756b'
    },
    night: {
      skyTop: '#111827', skyBottom: '#273469', hill: '#283b58',
      ground: '#1f4d4f', groundTop: '#2f6b64', obstacle: '#6d28d9',
      obstacleAccent: '#c4b5fd', platform: '#334155', platformAccent: '#64748b'
    },
    coast: {
      skyTop: '#bfe9ff', skyBottom: '#effbff', hill: '#9bd8cf',
      ground: '#efcf8d', groundTop: '#cfaa65', obstacle: '#0369a1',
      obstacleAccent: '#38bdf8', platform: '#52606d', platformAccent: '#7b8794'
    },
    autumn: {
      skyTop: '#f6dfbf', skyBottom: '#fff8ec', hill: '#d1a36f',
      ground: '#a87543', groundTop: '#79552f', obstacle: '#9a3412',
      obstacleAccent: '#fb923c', platform: '#5c5148', platformAccent: '#817268'
    }
  };

  function currentPalette() {
    return SCENE_PALETTES[state.scenario.key] || SCENE_PALETTES.meadow;
  }

  function drawBackground() {
    const palette = currentPalette();
    const g = ctx.createLinearGradient(0, 0, 0, canvas.height);
    g.addColorStop(0, palette.skyTop);
    g.addColorStop(1, palette.skyBottom);
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const scene = state.scenario.key;
    if (scene === 'night') {
      ctx.fillStyle = 'rgba(255,255,255,.78)';
      for (let i = 0; i < 28; i++) {
        const x = ((i * 83) - (state.distance * .05)) % 1040;
        const y = 28 + ((i * 47) % 180);
        ctx.fillRect(x, y, (i % 3) + 1, (i % 3) + 1);
      }
      ctx.fillStyle = '#f8fafc';
      ctx.beginPath(); ctx.arc(820, 82, 28, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = palette.skyTop;
      ctx.beginPath(); ctx.arc(832, 72, 24, 0, Math.PI * 2); ctx.fill();
    } else if (scene === 'sunset') {
      ctx.fillStyle = 'rgba(249,115,22,.7)';
      ctx.beginPath(); ctx.arc(820, 112, 46, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = 'rgba(255,255,255,.42)';
      for (let i = 0; i < 4; i++) {
        const x = ((i * 260) - (state.distance * .08)) % 1250;
        ctx.fillRect(x, 90 + (i % 2) * 45, 120, 8);
      }
    } else if (scene === 'coast') {
      ctx.fillStyle = '#67c6e8';
      ctx.fillRect(0, 278, canvas.width, 72);
      ctx.strokeStyle = 'rgba(255,255,255,.8)';
      ctx.lineWidth = 3;
      for (let row = 0; row < 3; row++) {
        ctx.beginPath();
        for (let x = 0; x <= canvas.width; x += 30) {
          const y = 294 + row * 17 + Math.sin((x + state.distance * .4) / 55) * 4;
          if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();
      }
    } else {
      ctx.fillStyle = 'rgba(255,255,255,.78)';
      for (let i = 0; i < 6; i++) {
        const x = ((i * 210) - (state.distance * .12)) % 1250;
        ctx.beginPath();
        ctx.arc(x, 75 + (i % 2) * 35, 28, 0, Math.PI * 2);
        ctx.arc(x + 32, 72 + (i % 2) * 35, 22, 0, Math.PI * 2);
        ctx.arc(x - 28, 82 + (i % 2) * 35, 20, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    ctx.fillStyle = palette.hill;
    ctx.beginPath();
    ctx.moveTo(0, 350);
    for (let x = 0; x <= 960; x += 80) {
      ctx.lineTo(x, 300 + Math.sin((x + state.distance * .2) / 130) * 22);
    }
    ctx.lineTo(960, 350); ctx.closePath(); ctx.fill();

    if (scene === 'autumn') {
      for (let i = 0; i < 8; i++) {
        const x = ((i * 145) - (state.distance * .22)) % 1120;
        ctx.fillStyle = '#6b4f2d'; ctx.fillRect(x, 274, 8, 76);
        ctx.fillStyle = i % 2 ? '#ea580c' : '#b45309';
        ctx.beginPath(); ctx.arc(x + 4, 265, 28, 0, Math.PI * 2); ctx.fill();
      }
    }

    ctx.fillStyle = palette.ground;
    ctx.fillRect(0, 350, canvas.width, 70);
    ctx.fillStyle = palette.groundTop;
    ctx.fillRect(0, 350, canvas.width, 8);
  }

  function drawWorld(now) {
    for (const platform of state.platforms) {
      const x = screenX(platform.at);
      const palette = currentPalette();
      ctx.fillStyle = palette.platform;
      ctx.fillRect(x, platform.y, platform.w, 14);
      ctx.fillStyle = palette.platformAccent;
      ctx.fillRect(x + 5, platform.y + 14, platform.w - 10, 8);
    }

    for (const o of state.obstacles) {
      const x = screenX(o.at), y = 350 - o.h;
      const palette = currentPalette();
      ctx.fillStyle = palette.obstacle;
      ctx.fillRect(x, y, o.w, o.h);
      ctx.fillStyle = palette.obstacleAccent;
      ctx.fillRect(x + 5, y + 6, Math.max(4, o.w - 10), 7);
    }

    const p = state.player;
    const blink = now < state.invincibleUntil && Math.floor(now / 90) % 2 === 0;
    if (!blink) {
      ctx.fillStyle = '#172554';
      ctx.fillRect(p.x, p.y + 8, p.w, p.h - 8);
      ctx.fillStyle = '#4f46e5';
      ctx.fillRect(p.x + 5, p.y, p.w - 10, 20);
      ctx.fillStyle = '#fff';
      ctx.fillRect(p.x + 9, p.y + 6, 5, 5);
      ctx.fillRect(p.x + 20, p.y + 6, 5, 5);
      ctx.fillStyle = '#fbbf24';
      ctx.fillRect(p.x + 5, p.y + p.h - 5, 9, 5);
      ctx.fillRect(p.x + 20, p.y + p.h - 5, 9, 5);
    }

    for (const particle of state.particles) {
      ctx.globalAlpha = Math.max(0, particle.life);
      ctx.fillStyle = '#f59e0b';
      ctx.fillRect(particle.x, particle.y, 5, 5);
    }
    ctx.globalAlpha = 1;

    const progress = Math.min(1, state.distance / state.targetDistance);
    ctx.fillStyle = 'rgba(23,32,51,.14)'; ctx.fillRect(700, 28, 210, 9);
    ctx.fillStyle = '#4f46e5'; ctx.fillRect(700, 28, 210 * progress, 9);
    ctx.fillStyle = '#172033'; ctx.font = '700 12px system-ui';
    ctx.fillText('FINISH', 916, 38);
  }

  async function requestChallenge(rescue = false) {
    if (!state.active || state.challengePending || state.currentChallenge) return;
    state.challengePending = true;
    state.paused = true;
    state.rescueChallenge = rescue;
    try {
      const url = urlForRun(app.dataset.challengeUrl, state.runId);
      const data = await jsonFetch(url, { method: 'POST', body: '{}' });
      state.currentChallenge = data.challenge;
      showChallenge(data.challenge);
    } catch (error) {
      console.error(error);
      state.challengePending = false;
      if (rescue) finishRun('failed'); else state.paused = false;
    }
  }

  function showChallenge(challenge) {
    state.challengePending = false;
    document.getElementById('challengeSource').textContent = `${challenge.source} · ${challenge.skill}`;
    document.getElementById('challengeDifficulty').textContent = `Difficulty ${challenge.difficulty}/5`;
    document.getElementById('challengePrompt').textContent = challenge.prompt;
    const options = document.getElementById('challengeOptions');
    options.innerHTML = '';
    for (const key of ['A','B','C','D']) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'challenge-option';
      button.dataset.option = key;
      button.innerHTML = `<span class="key">${key}</span><span>${escapeHtml(challenge.options[key])}</span>`;
      button.addEventListener('click', () => answerChallenge(key));
      options.appendChild(button);
    }
    document.getElementById('challengeFeedback').className = 'challenge-feedback';
    document.getElementById('challengeFeedback').textContent = '';
    continueButton.classList.remove('is-visible');
    challengeOverlay.classList.add('is-visible');
    challengeOverlay.setAttribute('aria-hidden', 'false');
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
  }

  async function answerChallenge(selected) {
    const challenge = state.currentChallenge;
    if (!challenge) return;
    const buttons = [...document.querySelectorAll('.challenge-option')];
    buttons.forEach(b => b.disabled = true);
    try {
      const url = urlForAnswer(app.dataset.answerUrl, state.runId, challenge.id);
      const data = await jsonFetch(url, { method: 'POST', body: JSON.stringify({ selected_option: selected }) });
      state.energy = Math.max(0, Math.min(100, state.energy + data.energy_delta));
      state.score = data.score;
      updateHud();
      buttons.forEach(button => {
        if (button.dataset.option === data.correct_option) button.classList.add('is-correct');
        if (button.dataset.option === selected && !data.correct) button.classList.add('is-wrong');
      });
      const feedback = document.getElementById('challengeFeedback');
      feedback.className = `challenge-feedback is-visible ${data.correct ? 'correct' : 'wrong'}`;
      feedback.innerHTML = `<strong>${data.correct ? 'Correct! Energy restored.' : 'Not quite.'}</strong><br>${escapeHtml(data.explanation || '')}`;
      continueButton.classList.add('is-visible');
      continueButton.dataset.canContinue = (data.correct || !state.rescueChallenge || state.energy > 0) ? '1' : '0';
      continueButton.textContent = continueButton.dataset.canContinue === '1' ? 'Continue running →' : 'Finish run';
    } catch (error) {
      buttons.forEach(b => b.disabled = false);
      alert(`Could not submit the answer: ${error.message}`);
    }
  }

  function closeChallenge() {
    const canContinue = continueButton.dataset.canContinue === '1';
    challengeOverlay.classList.remove('is-visible');
    challengeOverlay.setAttribute('aria-hidden', 'true');
    state.currentChallenge = null;
    state.rescueChallenge = false;
    if (!canContinue || state.energy <= 0) {
      finishRun('failed');
      return;
    }
    state.nextChallengeAt = Math.max(state.nextChallengeAt + state.challengeInterval, state.distance + state.challengeInterval * .65);
    state.paused = false;
    state.lastTs = performance.now();
    requestAnimationFrame(loop);
  }

  async function finishRun(status) {
    if (state.finishing || !state.runId) return;
    state.finishing = true;
    state.active = false;
    state.paused = true;
    try {
      const url = urlForRun(app.dataset.finishUrl, state.runId);
      const data = await jsonFetch(url, { method: 'POST', body: JSON.stringify({ status, distance: state.distance, energy: state.energy }) });
      showEnd(data);
    } catch (error) {
      showEnd({ status: 'failed', score: state.score, distance: state.distance, correct: 0, questions: 0 });
    }
  }

  function showEnd(data) {
    const won = data.status === 'completed';
    document.getElementById('endTitle').textContent = won ? 'Run completed!' : 'Energy depleted';
    document.getElementById('endCopy').textContent = won
      ? `Great run. Tier ${state.tier} is complete; your next successful run will be more demanding.`
      : 'Review the challenge feedback and try again. Failed runs do not increase the difficulty tier.';
    document.getElementById('endScore').textContent = data.score || 0;
    document.getElementById('endQuestions').textContent = `${data.correct || 0}/${data.questions || 0}`;
    document.getElementById('endDistance').textContent = `${Math.floor(data.distance || 0)}/${state.targetDistance}`;
    const icon = document.querySelector('#endIcon i');
    icon.className = won ? 'bi bi-trophy-fill' : 'bi bi-lightning-charge';
    endOverlay.classList.add('is-visible');
  }

  function updateParticles(dt) {
    for (const p of state.particles) {
      p.x += p.vx * dt; p.y += p.vy * dt; p.vy += 190 * dt; p.life -= dt * 1.5;
    }
    state.particles = state.particles.filter(p => p.life > 0);
  }

  function loop(ts) {
    if (!state.active || state.paused) return;
    const dt = Math.min(.032, Math.max(.001, (ts - state.lastTs) / 1000));
    state.lastTs = ts;
    state.distance += state.speed * dt;
    state.energy -= state.energyDrain * dt;
    spawnWorld();
    physics(dt, ts);
    updateParticles(dt);
    drawBackground();
    drawWorld(ts);
    updateHud();

    if (state.distance >= state.targetDistance) {
      finishRun('completed');
      return;
    }
    if (state.energy <= 0) {
      state.energy = 0;
      updateHud();
      requestChallenge(true);
      return;
    }
    if (state.distance >= state.nextChallengeAt) {
      requestChallenge(false);
      return;
    }
    requestAnimationFrame(loop);
  }

  window.addEventListener('keydown', (event) => {
    if (['Space','ArrowUp','KeyW'].includes(event.code)) {
      event.preventDefault();
      jump();
    }
  });
  canvas.addEventListener('pointerdown', jump);
  jumpButton.addEventListener('click', jump);
  startButton.addEventListener('click', startRun);
  playAgainButton.addEventListener('click', startRun);
  continueButton.addEventListener('click', closeChallenge);

  drawBackground();
  drawWorld(performance.now());
  updateHud();
})();
