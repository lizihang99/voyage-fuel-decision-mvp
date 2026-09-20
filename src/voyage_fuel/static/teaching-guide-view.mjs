function isVisible(element) {
  return Boolean(element?.isConnected && element.getClientRects().length);
}


function noteElement(note) {
  const container = document.createElement("aside");
  container.className = "teaching-guide-note";
  container.dataset.guideNote = note.id;
  const title = document.createElement("strong");
  title.textContent = note.title;
  const text = document.createElement("p");
  text.textContent = note.text;
  container.append(title, text);
  return container;
}


export function createTeachingGuideView({ root = document, onVisibilityChange } = {}) {
  let mounted = [];
  let observer = null;
  let frame = null;

  function clearMount() {
    if (frame !== null && typeof cancelAnimationFrame === "function") {
      cancelAnimationFrame(frame);
    }
    frame = null;
    observer?.disconnect();
    observer = null;
    mounted.forEach(({ element, anchor }) => {
      element.remove();
      if (anchor.dataset.guideActive === "true") {
        delete anchor.dataset.guideActive;
      }
    });
    mounted = [];
  }

  function updateActive() {
    frame = null;
    if (!mounted.length) return;
    const visible = mounted.filter(({ element }) => isVisible(element));
    if (!visible.length) {
      mounted.forEach(({ anchor }) => {
        if (anchor.dataset.guideActive === "true") delete anchor.dataset.guideActive;
      });
      return;
    }
    const focusLine = (window.innerHeight || 0) * 0.4;
    let active = visible[0];
    let activeDistance = Number.POSITIVE_INFINITY;
    visible.forEach((candidate) => {
      const rect = candidate.element.getBoundingClientRect();
      const center = rect.top + rect.height / 2;
      const distance = Math.abs(center - focusLine);
      if (distance < activeDistance) {
        active = candidate;
        activeDistance = distance;
      }
    });
    mounted.forEach(({ anchor }) => {
      if (anchor === active.anchor) anchor.dataset.guideActive = "true";
      else if (anchor.dataset.guideActive === "true") delete anchor.dataset.guideActive;
    });
  }

  function scheduleUpdate() {
    if (frame !== null) return;
    if (typeof requestAnimationFrame === "function") {
      frame = requestAnimationFrame(updateActive);
    } else {
      updateActive();
    }
  }

  function mountNotes(notes) {
    const groups = new Map();
    notes.forEach((note) => {
      const group = groups.get(note.anchor) || [];
      group.push(note);
      groups.set(note.anchor, group);
    });
    groups.forEach((group, anchorName) => {
      const anchors = [...root.querySelectorAll(`[data-guide-anchor~="${anchorName}"]`)];
      const anchor = anchors.find(isVisible) || anchors[0];
      if (!anchor) return;
      const closedDetails = anchor.closest("details:not([open])");
      const target = closedDetails || (isVisible(anchor) ? anchor : anchor.closest("details") || anchor);
      [...group].reverse().forEach((note) => {
        const element = noteElement(note);
        target.insertAdjacentElement("afterend", element);
        mounted.push({ note, element, anchor: target });
      });
    });
    mounted.reverse();
  }

  function bindViewport() {
    if (typeof window === "undefined") return;
    window.addEventListener("scroll", scheduleUpdate, { passive: true });
    window.addEventListener("resize", scheduleUpdate);
    if (typeof IntersectionObserver === "function") {
      observer = new IntersectionObserver(scheduleUpdate, {
        rootMargin: "-20% 0px -40% 0px",
      });
      mounted.forEach(({ element }) => observer.observe(element));
    }
  }

  function unbindViewport() {
    if (typeof window === "undefined") return;
    window.removeEventListener("scroll", scheduleUpdate);
    window.removeEventListener("resize", scheduleUpdate);
  }

  return {
    render({ state, notes } = {}) {
      unbindViewport();
      clearMount();
      const visible = Boolean(state?.visible);
      onVisibilityChange?.(visible);
      if (!visible || !Array.isArray(notes) || !notes.length) return;
      mountNotes(notes);
      bindViewport();
      updateActive();
    },
    destroy() {
      unbindViewport();
      clearMount();
    },
  };
}
