Shader "ShiftLink/WorkerToon"
{
    Properties
    {
        _Color ("Palette", Color) = (1,1,1,1)
        _OutlineColor ("Outline", Color) = (0.008,0.016,0.045,1)
        _OutlineWidth ("Outline width (metres)", Range(0,0.01)) = 0.0025
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        // Mark filled pixels so the hull outlines only the outer silhouette.
        Stencil { Ref 1 ReadMask 1 WriteMask 1 Comp Always Pass Replace }
        CGPROGRAM
        #pragma surface surf Lambert fullforwardshadows
        #pragma target 3.0
        fixed4 _Color;
        struct Input { float3 worldPos; };
        void surf(Input IN, inout SurfaceOutput o)
        {
            o.Albedo = _Color.rgb;
            o.Emission = _Color.rgb * 0.18;
            o.Alpha = 1;
        }
        ENDCG
        Pass
        {
            Name "Outline"
            Cull Front
            Stencil { Ref 1 ReadMask 1 WriteMask 0 Comp NotEqual Pass Keep }
            ZWrite On
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"
            float _OutlineWidth;
            fixed4 _OutlineColor;
            struct appdata { float4 vertex : POSITION; float3 normal : NORMAL; };
            struct v2f { float4 position : SV_POSITION; };
            v2f vert(appdata v)
            {
                v2f o;
                v.vertex.xyz += v.normal * _OutlineWidth;
                o.position = UnityObjectToClipPos(v.vertex);
                return o;
            }
            fixed4 frag(v2f i) : SV_Target { return _OutlineColor; }
            ENDCG
        }
    }
    Fallback "Diffuse"
}
