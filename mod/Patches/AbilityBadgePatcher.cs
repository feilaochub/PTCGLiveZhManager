using HarmonyLib;
using System;
using System.Collections.Generic;
using System.Reflection;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace PTCGLiveZhMod.Patches
{
    // These two built-in sprites contain English pixels, rather than localized text.
    [HarmonyPatch]
    internal static class AbilityBadgePatcher
    {
        private const string LabelName = "PTCGLAbilityLabel";
        private static readonly Sprite[] Badges = new Sprite[2];
        private static TMP_FontAsset font;
        private static Material material;
        private static bool loggedFailure;

        internal static int BadgeState(string name)
        {
            switch (name)
            {
                case "atkOV_AbilityTag_Off":
                case "PTCGLAbilityTag_Off": return 0;
                case "atkOV_AbilityTag_On":
                case "PTCGLAbilityTag_On": return 1;
                default: return -1;
            }
        }

        [HarmonyTargetMethods]
        private static IEnumerable<MethodBase> TargetMethods()
        {
            yield return AccessTools.PropertySetter(typeof(Image), "sprite");
            yield return AccessTools.PropertySetter(typeof(Image), "overrideSprite");
        }

        [HarmonyPrefix]
        private static void TranslateSprite(ref Sprite value)
        {
            if (value == null) return;
            int state = BadgeState(value.name);
            if (state < 0) return;
            try
            {
                // Leave the original readable badge if the Chinese font cannot load.
                if (LoadFont()) value = GetBadge(state);
            }
            catch (Exception ex) { LogFailure(ex); }
        }

        [HarmonyPostfix]
        private static void RefreshLabel(Image __instance)
        {
            try
            {
                // overrideSprite's getter returns the effective sprite, including fallback.
                var active = __instance.overrideSprite;
                bool translated = active != null &&
                    (active.name == "PTCGLAbilityTag_Off" || active.name == "PTCGLAbilityTag_On");
                var child = __instance.transform.Find(LabelName);
                if (!translated)
                {
                    if (child != null) child.gameObject.SetActive(false);
                    return;
                }
                if (child == null)
                {
                    var go = new GameObject(LabelName, typeof(RectTransform));
                    go.layer = __instance.gameObject.layer;
                    go.transform.SetParent(__instance.transform, false);
                    go.AddComponent<LayoutElement>().ignoreLayout = true;
                    var label = go.AddComponent<TextMeshProUGUI>();
                    label.font = font;
                    label.fontSharedMaterial = material;
                    label.text = "特性";
                    label.color = Color.white;
                    label.fontStyle = FontStyles.Bold | FontStyles.Italic;
                    label.alignment = TextAlignmentOptions.Center;
                    label.enableWordWrapping = false;
                    label.enableAutoSizing = true;
                    // Some card canvases use world units instead of screen pixels.
                    label.fontSizeMin = 0.01f;
                    label.fontSizeMax = 64f;
                    label.fontSize = 36f;
                    label.overflowMode = TextOverflowModes.Truncate;
                    label.raycastTarget = false;
                    var presentation = __instance.gameObject.AddComponent<AbilityBadgePresentation>();
                    presentation.Image = __instance;
                    presentation.Label = label;
                    var rect = label.rectTransform;
                    rect.anchorMin = new Vector2(0.18f, 0.1f);
                    rect.anchorMax = new Vector2(0.82f, 0.9f);
                    rect.offsetMin = Vector2.zero;
                    rect.offsetMax = Vector2.zero;
                    child = rect;
                }
                child.gameObject.SetActive(__instance.isActiveAndEnabled);
            }
            catch (Exception ex) { LogFailure(ex); }
        }

        internal static void TranslateSerializedBadge(Image __instance)
        {
            try
            {
                var sprite = __instance.sprite;
                if (sprite != null && BadgeState(sprite.name) >= 0)
                    __instance.sprite = sprite;
                var active = __instance.overrideSprite;
                if (active != null && (active.name == "atkOV_AbilityTag_Off" || active.name == "atkOV_AbilityTag_On"))
                    __instance.overrideSprite = active;
                RefreshLabel(__instance);
            }
            catch (Exception ex) { LogFailure(ex); }
        }

        private static bool LoadFont()
        {
            if (font != null && material != null) return true;
            return AssetBundleManagerX.LoadFontAssets(out font, out material);
        }

        private static Sprite GetBadge(int state)
        {
            if (Badges[state] != null) return Badges[state];
            const int width = 256, height = 64;
            var texture = new Texture2D(width, height, TextureFormat.RGBA32, false);
            texture.name = "PTCGLAbilityBackground";
            texture.filterMode = FilterMode.Bilinear;
            texture.wrapMode = TextureWrapMode.Clamp;
            var pixels = new Color32[width * height];
            for (int y = 0; y < height; y++)
            for (int x = 0; x < width; x++)
            {
                float dx = Math.Max(Math.Abs(x - 127.5f) - 96f, 0f);
                float dy = y - 31.5f;
                float distance = (float)Math.Sqrt(dx * dx + dy * dy);
                if (distance > 31.5f) continue;
                byte alpha = (byte)(255f * Math.Min(31.5f - distance, 1f));
                if (distance > 27.5f) pixels[y * width + x] = new Color32(210, 210, 210, alpha);
                else if (state == 1) pixels[y * width + x] = new Color32((byte)(165 + y), 30, 36, alpha);
                else pixels[y * width + x] = new Color32((byte)(85 + y), (byte)(85 + y), (byte)(85 + y), alpha);
            }
            texture.SetPixels32(pixels);
            texture.Apply(false, true);
            var badge = Sprite.Create(texture, new Rect(0, 0, width, height), new Vector2(0.5f, 0.5f), 100f);
            badge.name = state == 1 ? "PTCGLAbilityTag_On" : "PTCGLAbilityTag_Off";
            UnityEngine.Object.DontDestroyOnLoad(texture);
            UnityEngine.Object.DontDestroyOnLoad(badge);
            Badges[state] = badge;
            return badge;
        }

        private static void LogFailure(Exception ex)
        {
            if (loggedFailure) return;
            loggedFailure = true;
            Plugin.LoggerInstance.LogError("Ability badge localization failed: " + ex);
        }
    }

    [HarmonyPatch(typeof(Image), "OnEnable")]
    internal static class AbilityBadgeEnablePatcher
    {
        [HarmonyPostfix]
        private static void OnEnable(Image __instance)
        {
            AbilityBadgePatcher.TranslateSerializedBadge(__instance);
        }
    }

    // Image.enabled and Image.color do not automatically affect child text.
    // Keep the overlay in step with the game's own hide/fade animation.
    internal sealed class AbilityBadgePresentation : MonoBehaviour
    {
        internal Image Image;
        internal TextMeshProUGUI Label;

        private void LateUpdate()
        {
            if (Image == null || Label == null) return;
            var sprite = Image.overrideSprite;
            bool visible = Image.isActiveAndEnabled && sprite != null &&
                (sprite.name == "PTCGLAbilityTag_Off" || sprite.name == "PTCGLAbilityTag_On");
            if (Label.gameObject.activeSelf != visible) Label.gameObject.SetActive(visible);
            if (visible && Label.color.a != Image.color.a)
                Label.color = new Color(1f, 1f, 1f, Image.color.a);
        }

        private void OnDisable()
        {
            if (Label != null) Label.gameObject.SetActive(false);
        }
    }
}
