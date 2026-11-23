' 원본: setCad.bas (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Public Module setCad

    Public Sub SetACAD(ByVal ModuleName As String, ByVal DimSc As Double)
        Dim dimscale As Double


        If ModuleName = "FanDrawing" Then
            dimscale = DimSc * 0.75

        ElseIf ModuleName = "Performance" Then
            dimscale = 1
        End If

        '시스템변수 조정
        ThisDrawing.SetVariable("dimscale", dimscale)
        ThisDrawing.SetVariable("ltscale", 0.25)
        ThisDrawing.SetVariable("celtscale", 1)

        ThisDrawing.SetVariable("dimaunit", 0)
        ThisDrawing.SetVariable("dimaso", 1)
        ThisDrawing.SetVariable("dimasz", 3.2)
        ThisDrawing.SetVariable("dimclrd", 40)
        ThisDrawing.SetVariable("dimclre", 40)
        ThisDrawing.SetVariable("dimclrt", 2)
        ThisDrawing.SetVariable("dimdec", 0)
        ThisDrawing.SetVariable("dimexe", 1.5)
        ThisDrawing.SetVariable("dimexo", 1.5)
        ThisDrawing.SetVariable("dimfit", 3)
        ThisDrawing.SetVariable("dimgap", 1#)

        ThisDrawing.SetVariable("dimtad", 1)
        ThisDrawing.SetVariable("dimtih", 0)
        ThisDrawing.SetVariable("dimtoh", 0)
        ThisDrawing.SetVariable("dimtix", 0)
        ThisDrawing.SetVariable("dimtxsty", "standard")

        If ModuleName = "FanDrawing" Then
            ThisDrawing.SetVariable("dimtxt", 4#)
            ElseIf ModuleName = "Performance" Then
                ThisDrawing.SetVariable("dimtxt", 3.2)
        End If
        ThisDrawing.SetVariable("dimunit", 2)

        ThisDrawing.SetVariable("gripcolor", 60)
        ThisDrawing.SetVariable("gripsize", 5)
        ThisDrawing.SetVariable("highlight", 1)

        ThisDrawing.SetVariable("mirrtext", 0)
        ThisDrawing.SetVariable("osmode", 111)
        ThisDrawing.SetVariable("pdmode", 35)
        ThisDrawing.SetVariable("pdsize", -2.5)

        If ModuleName = "FanDrawing" Then
            ThisDrawing.SetVariable("textsize", (dimscale * 4#))
        ElseIf ModuleName = "Performance" Then
            ThisDrawing.SetVariable("textsize", (dimscale * 3.2))
        End If

        ThisDrawing.SetVariable("textstyle", "standard")
        ThisDrawing.Application.Update

    End Sub

    Sub VariablesSetting()
        Dim SCL As Double

        'CMLSCALE <20> : 멀티라인의 스케일을 1로 조정한다.
        ThisDrawing.SetVariable("CMLSCALE", 1)

            SCL = ThisDrawing.GetVariable("DIMSCALE")

        '==========================================================================================
        '치수변수 설정
        '==========================================================================================
        'DIMADEC <0> : 표시되는 각도의 소수점 자리를 지정한다.
        ThisDrawing.SetVariable("DIMADEC", 2)

        'DIMALT <0> : 치수 기입시 두 단위계의 치수 표시 여부를 조절한다.
        '0 = 하나의 단위계만 표시한다.
        '1 = 두 단위계를 모두 표시한다.
        ThisDrawing.SetVariable("DIMALT", 0)

        'DIMALTD <2> : 치수 기입시 두 단위계를 사용할 때 []안의 소수점 자리수를 조절한다.
        ThisDrawing.SetVariable("DIMALTD", 2)

        'DIMALTF <25.4> : 치수 기입시 DIMALT 변수가 ON일 때 현재 치수에 곱해지는 배수를 지정한다.
        ThisDrawing.SetVariable("DIMALTF", 25.4)

        'DIMALTTD <2> : 치수 기입시 두 단위계를 사용할 때 적용되는 허용 오차 값의 소수점 자리수를 지정한다.
        ThisDrawing.SetVariable("DIMALTTD", 2)

        'DIMALTTZ <0> : 허용 오차 값의 0 값에 대해 억제를 조절한다.
        ThisDrawing.SetVariable("DIMALTTZ", 0)

        'DIMALTU <2> : 선형치수의 두 단위계에 대한 단위 형식을 지정한다.
        '1 = 지수표시
        '2 = 소수표시
        '3 = 기계표시
        '4 = 건축표시
        '5 = 분수표시
        ThisDrawing.SetVariable("DIMALTU", 2)

        'DIMALTZ <0> : 두 단위계에 대한 0의 억제를 조절한다.
        '0 = 0을 억제하지 않는다.
        '1 = 0을 억제한다.
        ThisDrawing.SetVariable("DIMALTZ", 0)

        'DIMASO <1> : 치수 EXPLODE의 기능 여부를 조절한다.
        '0 = 개별요소로 치수가 기입된다.
        '1 = 블록형태로 치수가 기입된다.
        ThisDrawing.SetVariable("DIMASO", 1)

        'DIMPOST <""> : DIMALT 변수가 ON일 때 []안에 나타나는 치수되에 붙는 문자를 지정한다.
        ThisDrawing.SetVariable("DIMPOST", "")

        'DIMASZ <0.18> : 화살표의 크기를 조절한다.
        ThisDrawing.SetVariable("DIMASZ", 2.5)

        'DIMAUNIT <0> : 각도 치수의 기입 형태를 조절한다.
        '0 = 십진각도
        '1 = 도/분/초
        '2 = 그래드
        '3 = 라디안
        ThisDrawing.SetVariable("DIMAUNIT", 0)

        'DIMAZIN <0> : Suppresses zeros for angular dimensions.
        '0 = Displays all leading and trailing zeros
        '1 = Suppresses leading zeros in decimal dimensions (for example, 0.5000 becomes .5000)
        '2 = Suppresses trailing zeros in decimal dimensions (for example, 12.5000 becomes 12.5)
        '3 = Suppresses leading and trailing zeros  (for example, 0.5000 becomes .5)
        ThisDrawing.SetVariable("DIMAZIN", 2)

        'DIMBLK <""> : 치수선 끝에 표시되는 심벌의 형태를 지정한다.
        'ThisDrawing.SetVariable "DIMBLK", ""

        'DIMBLK1 <""> : DIMSAH가 ON일 때 첫 번째 치수선 끝에 나타나는 심벌을 지정한다.
        'ThisDrawing.SetVariable "DIMBLK1", ""

        'DIMBLK2 <""> : DIMSAH가 ON일 때 두 번째 치수선 끝에 나타나는 심벌을 지정한다.
        'ThisDrawing.SetVariable "DIMBLK2", ""

        'DIMCEN <0.09> : 원, 호 등의 중심점을 나타낼 때 생성되는 중심마크의 크기를 지정한다.
        ThisDrawing.SetVariable("DIMCEN", 0.09 * SCL)

        'DIMCLRD <0> : 치수선의 색상을 지정한다.
        ThisDrawing.SetVariable("DIMCLRD", 40)

        'DIMCLRE <0> : 치수보조선의 색상을 지정한다.
        ThisDrawing.SetVariable("DIMCLRE", 40)

        'DIMCLRT <0> : 치수의 색상을 지정한다.
        ThisDrawing.SetVariable("DIMCLRT", 2)

        'DIMDEC <4> : 공차값에 대한 소수점 자리를 지정한다.
        ThisDrawing.SetVariable("DIMDEC", 2)

        'DIMDLE <0.00> : 기수기입시 TICK로 표시할 때 치수보조선으로부터 벗어나는 TICK의  길이를 조절한다.
        ThisDrawing.SetVariable("DIMDLE", 0)

        'DIMDLI <0.38> : 기준선과 CONTINUE 치수의  치수선과 치수선의 간격을 지정한다.
        ThisDrawing.SetVariable("DIMDLI", 7)

        'DIMDSEP <,> : Specifies a single-character decimal separator to use when creating dimensions whose
        '                       unit format is decimal.
        '                       When prompted, enter a single character at the command line. If dimension units is set to
        '                       Decimal, the DIMDSEP character is used instead of the default decimal point. If DIMDSEP is
        '                       set to NULL (default value, reset by entering a period), AutoCAD uses the decimal point as
        '                       the dimension separator.
        ThisDrawing.SetVariable("DIMDSEP", ".")


        'DIMEXE <0.18> : 치수보조선이 치수선 밖으로 벗어나는 길이를 조절한다.
        ThisDrawing.SetVariable("DIMEXE", 1#)

        'DIMEXO <0.0625> : 측정 물체에서 치수보조선이 떨어지는 값을 조절한다.
        ThisDrawing.SetVariable("DIMEXO", 1#)

        'DIMFIT <3> : 치수보조선의 여유공간에 근거하여 문자, 화살표의 위치를 조절하는 데 관련된 변수이다.
        '0 = 공간이 여유가 있으면, 치수보조선 안에 문자와 화살표를 위치시키고, 그렇지 않으면 치수보조선
        '      밖에  위치시킨다.
        '1 = 공간에 여유가 있다면 0과 같으나 여유가 없을 경우에는 문자는 치수보조선 안에 화살표는 경우에
        '     따라 안과 밖에 위치시킨다.
        '2 = 공간에 여유가 있을 경우에는 0과 같으나 여유가 없을 경우 문자가 들어갈 여유가 있는가 판단하여
        '      있다면 문자를 치수보조선 안에 화살표는 밖에 위치시킨다.
        '      공간이 화살표만 치수보조선 안에 위치시킬수 있다면 화살표는 치수보조선 안에 치수는 치수보조선
        '      밖에 위치시킨다.
        '3 = 치수보조선 안에 가장 적당한 자리에 위치시킨다.
        '4 = 치수보조선 안에 치수가 들어가지 못하면 지시선을 사용하여 표시한다.
        ThisDrawing.SetVariable("DIMFIT", 3)

        'DIMGAP <0.09> : 치수선과 치수의 간격을 조절한다.
        ThisDrawing.SetVariable("DIMGAP", 1#)

        'DIMLFAC <1.0> : 모든 치수에 곱해질 일정 배수를 지정한다.
        ThisDrawing.SetVariable("DIMLFAC", 1#)

        'DIMJUST <0> : 수평치수의 문자위치를 지정한다.
        '0 = 치수보조선 안 중앙에 치수를 위치시킨다.
        '1 = 첫 번째 치수보조선 옆에 치수를 위치시킨다.
        '2 = 두 번째 치수보조선 옆에 치수를 위치시킨다.
        '3 = 첫 번째 치수보조선 위에 치수를 위치시킨다.
        '4 = 두 번째 치수보조선 위에 치수를 위치시킨다.
        ThisDrawing.SetVariable("DIMJUST", 0)

        'DIMLIM <0> : 치수의 한계값 표시여부를 조절한다.
        '0 = 치수의 한계값을 표시하지 않는다.
        '1 = 치수의 한계값을 표시한다.
        ThisDrawing.SetVariable("DIMLIM", 0)

        'DIMPOST <""> : 치수 뒤에 붙는 문자를 지정한다.
        ThisDrawing.SetVariable("DIMPOST", "")

        'DIMRND <0.0000> : 치수 기입시 측정한 치수를 반올림한다.
        ThisDrawing.SetVariable("DIMRND", 0#)

        'DIMSAH <0> : 치수선 끝에 나타나는 심벌의 종류를 각기 다르게 지정할 수 있도록 지원해 준다.
        '0 = 다른 심벌을 사용할 수 없다.
        '1 = 다른 심벌을 사용할 수 있다.
        ThisDrawing.SetVariable("DIMSAH", 0)

        'DIMSD1 <0> : 첫 번째 치수선의 표시여부를 지정한다.
        '0 = 첫 번째 치수선을 표시한다.
        '1 = 첫 번째 치수선을 표시하지 않는다.
        ThisDrawing.SetVariable("DIMSD1", 0)

        'DIMSD2 <0> : 두 번째 치수선의 표시여부를 지정한다.
        '0 = 두 번째 치수선을 표시한다.
        '1 = 두 번째 치수선을 표시하지 않는다.
        ThisDrawing.SetVariable("DIMSD2", 0)

        'DIMSE1 <0> : 첫 번째 치수보조선의 표시여부를 지정한다.
        '0 = 첫 번째 치수보조선을 표시한다.
        '1 = 첫 번째 치수보조선을 표시하지 않는다.
        ThisDrawing.SetVariable("DIMSE1", 0)

        'DIMSE2 <0> : 두 번째 치수보조선의 표시여부를 지정한다.
        '0 = 두 번째 치수보조선을 표시한다.
        '1 = 두 번째 치수보조선을 표시하지 않는다.
        ThisDrawing.SetVariable("DIMSE2", 0)

        'DIMSHO <1> : STRETCH 명령으로 치수의 크기를 변경할 때 치수의 자동 변경여부를 결정한다.
        '0 = 치수가 변하지 않는다.
        '1 = 치수가 자동으로 변한다.
        ThisDrawing.SetVariable("DIMSHO", 1)

        'DIMSOXD <0> : DIMTIX가 ON일 때 치수선의 치수보조선에 대한 연장 여부를 조절한다.
        '0 = 치수보조선 밖으로 연장된다.
        '1 = 치수보조선 밖으로 연장되지 않는다.
        ThisDrawing.SetVariable("DIMSOXD", 0)

        'DIMTAD <0> : 치수선에 대한 치수의 위치를 지정한다.
        '0 = 치수가 치수선 안에 위치한다.
        '1 = 치수가 치수선 위에 위치한다.
        ThisDrawing.SetVariable("DIMTAD", 1)

        'DIMTDEC <4> : 공차의 소수점 자리수를 지정한다.
        ThisDrawing.SetVariable("DIMTDEC", 2)

        'DIMTFAC <1.0000> : 공차 값의 문자 높이를 치수 문자의 높이 값에 대한 비율로 지정한다.
        ThisDrawing.SetVariable("DIMTFAC", 0.7)

        'DIMTIH <0> :  치수선 안의 치수와 치수선과의 평행여부를 지정한다.
        '0 = 평행하게 한다.
        '1 = 평행하지 않게 한다.
        ThisDrawing.SetVariable("DIMTIH", 0)

        'DIMTIX <0> : 치수보조선의 여유에 따라 치수기입 여부를 조정한다.
        '0 = 치수를 치수보조선 밖에 표시한다.
        '1 = 치수를 치수보조선 안에 표시한다.
        ThisDrawing.SetVariable("DIMTIX", 0)

        'DIMTOFL <0> : 치수보조선의 여유에 따라 치수선의 표시여부를 조정한다.
        '0 = 치수선을 치수보조선 안에 표시하지 않는다.
        '1 = 치수선을 치수보조선 안에 연장하여 표시한다.
        ThisDrawing.SetVariable("DIMTOFL", 1)

        'DIMTOH <1> : 치수보조선 밖의 치수와 치수선과의 평행여부를 조정한다.
        '0 = 평행하게 표시한다.
        '1 = 평행하지 않게 표시한다.
        ThisDrawing.SetVariable("DIMTOH", 0)

        'DIMTOL <0> : 공차의 표시를 조정한다.
        '0 = 공차를 표시하지 않는다.
        '1 =공차를 표시한다.
        ThisDrawing.SetVariable("DIMTOL", 0)

        'DIMTP <0.0000> : + 허용공차의 값을 지정한다.
        ThisDrawing.SetVariable("DIMTP", 0#)

        'DIMTM <0.0000> : - 허용공차의 값을 지정한다.
        ThisDrawing.SetVariable("DIMTM", 0#)

        'DIMTMOVE <0> : - 치수 이동규칙
        ThisDrawing.SetVariable("DIMTMOVE", 0)

        'DIMTSZ <0.0000> : TICK를 사용하여 치수를 기입할 경우 TICK의 크기를 지정한다.
        ThisDrawing.SetVariable("DIMTSZ", 0#)

        'DIMTVP <0.0000> : 치수와 치수선과의 거리를 조정한다. DIMTAD가 OFF일 때 유효하다.
        '양의 값을 입력하면 치수선 위쪽에 음의 값을 입력하면 치수선 아래쪽으로 표시된다.
        ThisDrawing.SetVariable("DIMTVP", 0#)

        'DIMTXSTY <"Standard"> : 치수문자의 스타일을 지정한다.
        'ThisDrawing.SetVariable "DIMTXSTY", "Standard"

        'DIMTXT <0.18> : 치수의 크기를 조절한다.
        ThisDrawing.SetVariable("DIMTXT", 3#)

        'DIMTZIN <0> : 공차의 표시에 있어 0의 표시를 지정한다.
        '0 = 0을 표시하지 않는다.
        '1 = 0을 표시한다.
        ThisDrawing.SetVariable("DIMTZIN", 0)

        'DIMUNIT <2> : 선형치수에 대한 단위표시 형태를 지정한다.
        '1 = 지수표시
        '2 = 소수표시
        '3 = 기계표시
        '4 = 건축표시
        '5 = 분수표시
        ThisDrawing.SetVariable("DIMUNIT", 2)

        'DIMUPT <0> : 사용자 위치 문자에 대한 커서의 기능을 조절한다.
        '0 = 커서는 치수선 위치 만을 조절한다.
        '1 = 커서는 치수선의 위치뿐만 아니라 문자의 위치도 조절한다.
        ThisDrawing.SetVariable("DIMUPT", 0)

        'DIMZIN <0> : Controls the suppression of zeros in tolerance values. DIMTZIN stores this value
        '                    when you enter it on the command line or set it under Primary Units in the Annotation
        '                    dialog box. DIMTZIN values 0~3 affect feet-and-inch dimensions only.
        '0 = Suppresses zero feet and precisely zero inches
        '1 = Includes zero feet and precisely zero inches
        '2 = Includes zero feet and suppresses zero inches
        '3 = Includes zero inches and suppresses zero feet
        '4 = Suppresses leading zeros in decimal dimensions (for example, 0.5000 becomes .5000)
        '8 = Suppresses trailing zeros in decimal dimensions (for example, 12.5000 becomes 12.5)
        '12 = Suppresses both leading and trailing zeros (for example, 0.5000 becomes 0.5)
        ThisDrawing.SetVariable("DIMZIN", 8)


        '==========================================================================================
        '기타 주요 시스템변수 설정
        '==========================================================================================

        'CHANFERA <0.5> : Sets the first chamfer distance.
        ThisDrawing.SetVariable("CHAMFERA", 0#)

        'CHANFERB <0.5> : Sets the second chamfer distance.
        ThisDrawing.SetVariable("CHAMFERB", 0#)

        'CHANFERC <1.0> : Sets the chamfer length.
        ThisDrawing.SetVariable("CHAMFERC", 0#)

        'CHANFERD <0.5> : Sets the chamfer angle.
        ThisDrawing.SetVariable("CHAMFERD", 0#)

        'CHAMMODE <0> : Sets the input method by which AutoCAD creates chamfers.
        '0 = Requires two chamfer distances
        '1 = Requires one chamfer distance and an angle
        ThisDrawing.SetVariable("CHAMMODE", 0)

        'FILLETRAD <0> : Stores the current fillet radius.
        ThisDrawing.SetVariable("FILLETRAD", 0#)

        If ThisDrawing.GetVariable("LTSCALE") <> SCL * 0.25 Then
            'LTSCALE
            ThisDrawing.SetVariable("LTSCALE", SCL * 0.25)
        End If

        If ThisDrawing.GetVariable("OSMODE") <> 111 Then
            'OSMODE
            ThisDrawing.SetVariable("OSMODE", 111)
        End If


        If ThisDrawing.GetVariable("PDMODE") <> 35 Then
            'PDMODE
            ThisDrawing.SetVariable("PDMODE", 35)
        End If

        If ThisDrawing.GetVariable("PDSIZE") <> 0 Then
            'PDSIZE
            ThisDrawing.SetVariable("PDSIZE", 0)
        End If


        'TEXTSIZE <0.2> : Sets the default height for new text objects drawn with the current text style
        '                           (has no effect if the style has a fixed height).
        ThisDrawing.SetVariable("TEXTSIZE", SCL * 3#)
        ThisDrawing.SetVariable("INSUNITS", 0)

        'UCSICON <1> : Displays the UCS icon for the current viewport using bitcode. UCSICON is both a command
        '                        and a system variable. It is the sum of the following:
            '0 = No icon displayed
            '1 = On; icon is displayed
            '2 = Origin; if icon is displayed, the icon floats to the UCS origin if possible
            '3 = On and displayed at origin.
        'The UCSICON command controls the visibility and placement of the UCS icon. Because entering ucsicon
        'at the Command prompt invokes the UCSICON command, you must use the SETVAR command to access
        'the UCSICON system variable.
        ThisDrawing.SetVariable("UCSICON", 0)


        '==========================================================================================
        '설정 반영하기
        '==========================================================================================
        'Standard TextStyle에 대한 설정
        ThisDrawing.TextStyles("Standard").fontFile = "romans.shx"
        ThisDrawing.TextStyles("Standard").Width = 0.8


        ThisDrawing.SetVariable("CMDECHO", 1)
        ThisDrawing.Utility.Prompt(vbCrLf)
        ThisDrawing.Utility.Prompt("Setting was completed!")
        ThisDrawing.Utility.Prompt(vbCrLf)
        ThisDrawing.SetVariable("CMDECHO", 0)
        ThisDrawing.Regen(acActiveViewport)

    End Sub



End Module
